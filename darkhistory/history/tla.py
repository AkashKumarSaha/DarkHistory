"""Three-level atom model.

"""

import numpy as np
import darkhistory.physics as phys
import darkhistory.history.reionization as reion
from scipy.integrate import odeint
from scipy.integrate import solve_ivp
from scipy.misc import derivative

def compton_cooling_rate(xHII, xHeII, xHeIII, T_m, rs):
    """Returns the Compton cooling rate.

    Parameters
    ----------
    xHII : float
        n_HII/n_H.
    xHeII : float
        n_HeII/n_H.
    xHeIII : float
        n_HeIII/n_H.
    T_m : float
        The matter temperature.
    rs : float
        The redshift in 1+z.

    Returns
    -------
    float
        The Compton cooling rate in eV/s.

    Note
    ----
    This is the energy loss rate, *not* the temperature loss rate.

    """
    xe = xHII + xHeII + 2*xHeIII

    return (
        4 * phys.thomson_xsec * 4 * phys.stefboltz / phys.me
        * xe * phys.nH*rs**3 * (phys.TCMB(rs) - T_m)
        * phys.TCMB(rs)**4
    )

def get_history(
    rs_vec, init_cond, f_H_ion=None, f_H_exc=None, f_heating=None,
    dm_injection_rate=None, reion_switch=True, reion_rs=None,
    photoion_rate_func=None, photoheat_rate_func=None,
    xe_reion_func=None, helium_TLA=False, f_He_ion=None, mxstep = 0
):
    """Returns the ionization and thermal history of the IGM.

    Parameters
    ----------
    init_cond : array
        Array containing [initial temperature, initial xHII, initial xHeII, initial xHeIII].
    f_H_ion : function or float, optional
        f(rs, x_HI, x_HeI, x_HeII) for hydrogen ionization. Treated as constant if float.
    f_H_exc : function or float, optional
        f(rs, x_HI, x_HeI, x_HeII) for hydrogen Lyman-alpha excitation. Treated as constant if float.
    f_heating : function or float, optional
        f(rs, x_HI, x_HeI, x_HeII) for heating. Treated as constant if float.
    dm_injection_rate : function or float, optional
        Injection rate of DM as a function of redshift. Treated as constant if float.
    rs_vec : ndarray
        Abscissa for the solution.
    reion_switch : bool
        Reionization model included if true.
    reion_rs : float, optional
        Redshift 1+z at which reionization effects turn on.
    photoion_rate_func : tuple of functions, optional
        Functions take redshift 1+z as input, return the photoionization rate in s^-1 of HI, HeI and HeII respectively. If not specified, defaults to `darkhistory.history.reionization.photoion_rate`. 
    photoheat_rate_func : tuple of functions, optional
        Functions take redshift 1+z as input, return the photoheating rate in s^-1 of HI, HeI and HeII respectively. If not specified, defaults to `darkhistory.history.reionization.photoheat_rate`. 
    xe_reion_func : function, optional
        Specifies a fixed ionization history after reion_rs.  
    helium_TLA : bool, optional
        Specifies whether to track helium before reionization. 
    f_He_ion : function or float, optional
        f(rs, x_HI, x_HeI, x_HeII) for helium ionization. Treated as constant if float. If None, treated as zero.
    mxstep : int, optional
        Maximum number of (internally defined) steps allowed for each integration point in t. See scipy.integrate.odeint

    Returns
    -------
    list of ndarray
        [temperature solution (in eV), xHII solution, xHeII, xHeIII].

    Note
    ----
    The actual differential equation that we solve is expressed in terms of y = arctanh(f*(x - f)), where f = 0.5 for x = xHII, and f = nHe/nH * 0.5 for x = xHeII or xHeIII, where nHe/nH is approximately 0.083.

    """

    # Defines the f(z) functions, which return a constant, 
    # if the input fz's are floats. 

    def _f_H_ion(rs, xHI, xHeI, xHeII):
        if f_H_ion is None:
            return 0.
        elif isinstance(f_H_ion, float) or isinstance(f_H_ion, int):
            return f_H_ion
        elif callable(f_H_ion):
            return f_H_ion(rs, xHI, xHeI, xHeII)
        else:
            raise TypeError('f_H_ion must be float or an appropriate function.')

    def _f_H_exc(rs, xHI, xHeI, xHeII):
        if f_H_exc is None:
            return 0
        elif isinstance(f_H_exc, float) or isinstance(f_H_exc, int):
            return f_H_exc
        elif callable(f_H_exc):
            return f_H_exc(rs, xHI, xHeI, xHeII)
        else:
            raise TypeError('f_H_exc must be float or an appropriate function.')

    def _f_heating(rs, xHI, xHeI, xHeII):
        if f_heating is None:
            return 0
        elif isinstance(f_heating, float) or isinstance(f_heating, int):
            return f_heating
        elif callable(f_heating):
            return f_heating(rs, xHI, xHeI, xHeII)
        else:
            raise TypeError('f_heating must be float or an appropriate function.')

    def _f_He_ion(rs, xHI, xHeI, xHeII):
        if f_He_ion is None:
            return 0.
        if isinstance(f_He_ion, float) or isinstance(f_He_ion, int):
            return f_He_ion
        elif callable(f_He_ion):
            return f_He_ion(rs, xHI, xHeI, xHeII)
        else:
            raise TypeError('f_He_ion must be float or an appropriate function.')

    def _dm_injection_rate(rs):
        if dm_injection_rate is None:
            return 0.
        elif isinstance(dm_injection_rate, float):
            return dm_injection_rate
        elif callable(dm_injection_rate):
            return dm_injection_rate(rs)
        else:
            raise TypeError('dm_injection_rate must be a float or an appropriate function.')

    chi = phys.chi

    if reion_switch:

        if photoion_rate_func is None:

            photoion_rate_HI   = reion.photoion_rate('HI')
            photoion_rate_HeI  = reion.photoion_rate('HeI')
            photoion_rate_HeII = reion.photoion_rate('HeII')

        else:

            photoion_rate_HI   = photoion_rate_func[0]
            photoion_rate_HeI  = photoion_rate_func[1]
            photoion_rate_HeII = photoion_rate_func[2]

    if reion_switch:

        if photoheat_rate_func is None:

            photoheat_rate_HI   = reion.photoheat_rate('HI')
            photoheat_rate_HeI  = reion.photoheat_rate('HeI')
            photoheat_rate_HeII = reion.photoheat_rate('HeII')

        else:

            photoheat_rate_HI   = photoheat_rate_func[0]
            photoheat_rate_HeI  = photoheat_rate_func[1]
            photoheat_rate_HeII = photoheat_rate_func[2]

    # Define conversion functions between x and y. 
    def xHII(yHII):
            return 0.5 + 0.5*np.tanh(yHII)
    def xHeII(yHeII):
        return chi/2 + chi/2*np.tanh(yHeII)
    def xHeIII(yHeIII):
        return chi/2 + chi/2*np.tanh(yHeIII)

    def tla_before_reion(rs, var):
        # Returns an array of values for [dT/dz, dyHII/dz,
        # dyHeII/dz, dyHeIII/dz].
        # var is the [temperature, xHII, xHeII, xHeIII] inputs.

        inj_rate = _dm_injection_rate(rs)
        nH = phys.nH*rs**3

        def dT_dz(yHII, yHeII, yHeIII, T_m, rs):

            xe = xHII(yHII) + xHeII(yHeII) + 2*xHeIII(yHeIII)
            xHI = 1 - xHII(yHII)
            xHeI = chi - xHeII(yHeII) - xHeIII(yHeIII)

            # This rate is temperature loss per redshift.
            adiabatic_cooling_rate = 2 * T_m/rs


            return adiabatic_cooling_rate + (
                - phys.dtdz(rs)*(
                    compton_cooling_rate(
                        xHII(yHII), xHeII(yHeII), xHeIII(yHeIII), T_m, rs
                    )
                    + _f_heating(rs, xHI, xHeI, xHeII(yHeII)) * inj_rate
                )
            )/ (3/2 * nH * (1 + chi + xe))


        def dyHII_dz(yHII, yHeII, yHeIII, T_m, rs):

            if 1 - xHII(yHII) < 1e-6 and rs < 100:
                # At this point, leave at 1 - 1e-6
                return 0
            # if yHII > 14. or yHII < -14.:
            #     # Stops the solver from wandering too far.
            #     return 0    
            if xHeII(yHeII) > 0.99*chi and rs > 1500:
                # This is prior to helium recombination.
                # Assume H completely ionized.
                return 0

            if xHII(yHII) > 0.99 and rs > 1000:
                # Use the Saha value. 
                return 2 * np.cosh(yHII)**2 * phys.d_xe_Saha_dz(rs, 'HI')


            xe = xHII(yHII) + xHeII(yHeII) + 2*xHeIII(yHeIII)
            ne = xe * nH
            xHI = 1 - xHII(yHII)
            xHeI = chi - xHeII(yHeII) - xHeIII(yHeIII)

            return 2 * np.cosh(yHII)**2 * -phys.dtdz(rs) * (
                # Recombination processes. 
                # Boltzmann factor is T_r, agrees with HyREC paper.
                - phys.peebles_C(xHII(yHII), rs) * (
                    phys.alpha_recomb(T_m, 'HI') * xHII(yHII) * xe * nH
                    - 4*phys.beta_ion(phys.TCMB(rs), 'HI') * xHI
                        * np.exp(-phys.lya_eng/phys.TCMB(rs))
                )
                # DM injection. Note that C = 1 at late times.
                + _f_H_ion(rs, xHI, xHeI, xHeII(yHeII)) * inj_rate
                    / (phys.rydberg * nH)
                + (1 - phys.peebles_C(xHII(yHII), rs)) * (
                    _f_H_exc(rs, xHI, xHeI, xHeII(yHeII)) * inj_rate
                    / (phys.lya_eng * nH)
                )
            )

        def dyHeII_dz(yHII, yHeII, yHeIII, T_m, rs):

            if not helium_TLA: 

                return 0

            if chi - xHeII(yHeII) < 1e-6 and rs < 100:
                # At this point, leave at 1 - 1e-6
                return 0
            
            # Stop the solver from reaching these extremes. 
            if yHeII > 14 or yHeII < -14:
                return 0

            # Use the Saha values at high ionization. 
            if xHeII(yHeII) > 0.99*chi: 

                return (
                    2/chi * np.cosh(yHeII)**2 * phys.d_xe_Saha_dz(rs, 'HeI')
                )

            xe = xHII(yHII) + xHeII(yHeII) + 2*xHeIII(yHeIII)
            ne = xe * nH
            xHI = 1 - xHII(yHII)
            xHeI = chi - xHeII(yHeII) - xHeIII(yHeIII)

            term_recomb_singlet = (
                xHeII(yHeII) * xe * nH * phys.alpha_recomb(T_m, 'HeI_21s')
            )
            term_ion_singlet = (
                phys.beta_ion(phys.TCMB(rs), 'HeI_21s')*(chi - xHeII(yHeII))
                * np.exp(-phys.He_exc_eng['21s']/phys.TCMB(rs))
            )

            term_recomb_triplet = (
                xHeII(yHeII) * xe * nH * phys.alpha_recomb(T_m, 'HeI_23s')
            )
            term_ion_triplet = (
                3*phys.beta_ion(phys.TCMB(rs), 'HeI_23s') 
                * (chi - xHeII(yHeII)) 
                * np.exp(-phys.He_exc_eng['23s']/phys.TCMB(rs))
            )

            return 2/chi * np.cosh(yHeII)**2 * -phys.dtdz(rs) * (
                -phys.C_He(xHII(yHII), xHeII(yHeII), rs, 'singlet') * (
                    term_recomb_singlet - term_ion_singlet
                )
                -phys.C_He(xHII(yHII), xHeII(yHeII), rs, 'triplet') * (
                    term_recomb_triplet - term_ion_triplet
                )
                + _f_He_ion(rs, xHI, xHeI, xHeII(yHeII)) * inj_rate
                    / (phys.He_ion_eng * nH)
            )

        def dyHeIII_dz(yHII, yHeII, yHeIII, T_m, rs):

            if chi - xHeIII(yHeIII) < 1e-6 and rs < 100:
                # At this point, leave at 1 - 1e-6
                return 0

            xe = xHII(yHII) + xHeII(yHeII) + 2*xHeIII(yHeIII)
            ne = xe * nH

            return 0

        T_m, yHII, yHeII, yHeIII = var[0], var[1], var[2], var[3]

        # print ([rs, 
        #     dT_dz(yHII, yHeII, yHeIII, T_m, rs),
        #     dyHII_dz(yHII, yHeII, yHeIII, T_m, rs),
        #     dyHeII_dz(yHII, yHeII, yHeIII, T_m, rs),
        #     dyHeIII_dz(yHII, yHeII, yHeIII, T_m, rs)
        # ])
        # print(rs, phys.peebles_C(xHII(yHII), rs))

        # print(rs, T_m, xHII(yHII), xHeII(yHeII), xHeIII(yHeIII))
        return [
            dT_dz(yHII, yHeII, yHeIII, T_m, rs),
            dyHII_dz(yHII, yHeII, yHeIII, T_m, rs),
            dyHeII_dz(yHII, yHeII, yHeIII, T_m, rs),
            dyHeIII_dz(yHII, yHeII, yHeIII, T_m, rs)
        ]

    def tla_reion(rs, var):
        # TLA with photoionization/photoheating reionization model.
        # Returns an array of values for [dT/dz, dyHII/dz,
        # dyHeII/dz, dyHeIII/dz].
        # var is the [temperature, xHII, xHeII, xHeIII] inputs.

        inj_rate = _dm_injection_rate(rs)
        nH = phys.nH*rs**3

        def dT_dz(yHII, yHeII, yHeIII, T_m, rs):

            xe = xHII(yHII) + xHeII(yHeII) + 2*xHeIII(yHeIII)
            xHI = 1 - xHII(yHII)
            xHeI = chi - xHeII(yHeII) - xHeIII(yHeIII)

            # This rate is temperature loss per redshift.
            adiabatic_cooling_rate = 2 * T_m/rs

            # The reionization rates and the Compton rate
            # are expressed in *energy loss* *per second*.

            photoheat_total_rate = nH * (
                xHI * photoheat_rate_HI(rs)
                + xHeI * photoheat_rate_HeI(rs)
                + xHeII(yHeII) * photoheat_rate_HeII(rs)
            )

            compton_rate = - phys.dtdz(rs)*(
                compton_cooling_rate(
                    xHII(yHII), xHeII(yHeII), xHeIII(yHeIII), T_m, rs
                )
            ) / (3/2 * nH * (1 + chi + xe))

            dm_heating_rate = - phys.dtdz(rs)*(
                _f_heating(rs, xHI, xHeI, xHeII(yHeII)) * inj_rate
            ) / (3/2 * nH * (1 + chi + xe))

            reion_rate = - phys.dtdz(rs) * (
                + photoheat_total_rate
                + reion.recomb_cooling_rate(
                    xHII(yHII), xHeII(yHeII), xHeIII(yHeIII), T_m, rs
                )
                + reion.coll_ion_cooling_rate(
                    xHII(yHII), xHeII(yHeII), xHeIII(yHeIII), T_m, rs
                )
                + reion.coll_exc_cooling_rate(
                    xHII(yHII), xHeII(yHeII), xHeIII(yHeIII), T_m, rs
                )
                + reion.brem_cooling_rate(
                    xHII(yHII), xHeII(yHeII), xHeIII(yHeIII), T_m, rs
                )
            ) / (3/2 * nH * (1 + chi + xe))

            return (
                adiabatic_cooling_rate + compton_rate 
                + dm_heating_rate + reion_rate
            )

        def dyHII_dz(yHII, yHeII, yHeIII, T_m, rs):

            if 1 - xHII(yHII) < 1e-6 and rs < 100:
                # At this point, leave at 1 - 1e-6
                return 0


            xe = xHII(yHII) + xHeII(yHeII) + 2*xHeIII(yHeIII)
            ne = xe * nH
            xHI = 1 - xHII(yHII)
            xHeI = chi - xHeII(yHeII) - xHeIII(yHeIII)

            return 2 * np.cosh(yHII)**2 * -phys.dtdz(rs) * (
                # DM injection. Note that C = 1 at late times.
                + _f_H_ion(rs, xHI, xHeI, xHeII(yHeII)) * (
                    inj_rate / (phys.rydberg * nH)
                )
                + (1 - phys.peebles_C(xHII(yHII), rs)) * (
                    _f_H_exc(rs, xHI, xHeI, xHeII(yHeII)) 
                    * inj_rate / (phys.lya_eng * nH)
                )
                # Reionization rates.
                + (
                    # Photoionization.
                    xHI * photoion_rate_HI(rs)
                    # Collisional ionization.
                    + xHI * ne * reion.coll_ion_rate('HI', T_m)
                    # Recombination.
                    - xHII(yHII) * ne * reion.alphaA_recomb('HII', T_m)
                )
            )

        def dyHeII_dz(yHII, yHeII, yHeIII, T_m, rs):

            if chi - xHeII(yHeII) < 1e-6 and rs < 100:
                # At this point, leave at 1 - 1e-6
                return 0

            xe = xHII(yHII) + xHeII(yHeII) + 2*xHeIII(yHeIII)
            ne = xe * nH
            xHI = 1 - xHII(yHII)
            xHeI = chi - xHeII(yHeII) - xHeIII(yHeIII)

            return 2/chi * np.cosh(yHeII)**2 * -phys.dtdz(rs) * (
                # Photoionization of HeI into HeII.
                xHeI * photoion_rate_HeI(rs)
                # Collisional ionization of HeI to HeII.
                + xHeI * ne * reion.coll_ion_rate('HeI', T_m)
                # Recombination of HeIII to HeII.
                + xHeIII(yHeIII) * ne * reion.alphaA_recomb('HeIII', T_m)
                # Photoionization of HeII to HeIII.
                - xHeII(yHeII) * photoion_rate_HeII(rs)
                # Collisional ionization of HeII to HeIII.
                - xHeII(yHeII) * ne * reion.coll_ion_rate('HeII', T_m)
                # Recombination of HeII into HeI.
                - xHeII(yHeII) * ne * reion.alphaA_recomb('HeII', T_m)
                # DM contribution
                + _f_He_ion(rs, xHI, xHeI, xHeII(yHeII)) * inj_rate
                    / (phys.He_ion_eng * nH)
            )

        def dyHeIII_dz(yHII, yHeII, yHeIII, T_m, rs):

            if chi - xHeIII(yHeIII) < 1e-6 and rs < 100:
                # At this point, leave at 1 - 1e-6
                return 0

            xe = xHII(yHII) + xHeII(yHeII) + 2*xHeIII(yHeIII)
            ne = xe * nH

            return 2/chi * np.cosh(yHeIII)**2 * -phys.dtdz(rs) * (
                # Photoionization of HeII into HeIII.
                xHeII(yHeII) * photoion_rate_HeII(rs)
                # Collisional ionization of HeII into HeIII.
                + xHeII(yHeII) * ne * reion.coll_ion_rate('HeII', T_m)
                # Recombination of HeIII into HeII.
                - xHeIII(yHeIII) * ne * reion.alphaA_recomb('HeIII', T_m)
            )

        T_m, yHII, yHeII, yHeIII = var[0], var[1], var[2], var[3]

        # print(rs, T_m, xHII(yHII), xHeII(yHeII), xHeIII(yHeIII))
        
        return [
            dT_dz(yHII, yHeII, yHeIII, T_m, rs),
            dyHII_dz(yHII, yHeII, yHeIII, T_m, rs),
            dyHeII_dz(yHII, yHeII, yHeIII, T_m, rs),
            dyHeIII_dz(yHII, yHeII, yHeIII, T_m, rs)
        ]

    def tla_reion_fixed_xe(rs, var):
        # TLA with fixed ionization history. 
        # Returns an array of values for [dT/dz, dyHII/dz].]. 
        # var is the [temperature, xHII] input.

        def dxe_dz(rs):

            return derivative(xe_reion_func, rs)

        def dT_dz(T_m, rs):

            xe  = xe_reion_func(rs)
            xHI = 1 - xe_reion_func(rs)

            # This is the temperature loss per redshift. 
            adiabatic_cooling_rate = 2 * T_m/rs

            return (
                adiabatic_cooling_rate
                + (
                    - phys.dtdz(rs)*(
                        compton_cooling_rate(xe, 0, 0, T_m, rs)
                        + _f_heating(rs, xHI, 0, 0) * _dm_injection_rate(rs)
                    )
                ) / (3/2 * phys.nH*rs**3 * (1 + chi + xe))
            )

        T_m = var

        return dT_dz(T_m, rs)

    _init_cond = np.array(init_cond)
    if init_cond[1] == 1:
        _init_cond[1] = 1 - 1e-12
    if init_cond[2] == 0:
        _init_cond[2] = 1e-12
    elif init_cond[2] == phys.chi:
        _init_cond[2] = (1. - 1e-12)*phys.chi
    if init_cond[3] == 0:
        _init_cond[3] = 1e-12


    _init_cond[1] = np.arctanh(2*(_init_cond[1] - 0.5))
    _init_cond[2] = np.arctanh(2/chi * (_init_cond[2] - chi/2))
    _init_cond[3] = np.arctanh(2/chi *(_init_cond[3] - chi/2))

    if reion_rs is None:
        reion_rs = 16.1

    rs_before_reion_vec = rs_vec[rs_vec > reion_rs]
    rs_reion_vec = rs_vec[rs_vec <= reion_rs]

    if not reion_switch:
        # No reionization model implemented.
        soln = odeint(
                tla_before_reion, _init_cond, rs_vec, 
                mxstep = mxstep, tfirst=True, rtol=1e-4
            )
        # print(init_cond)
        # print(rs_vec)
        # soln = solve_ivp(
        #     tla_before_reion, [rs_vec[0], rs_vec[-1]],
        #     init_cond, method='Radau'
        # )
        # print(soln)
    elif xe_reion_func is not None:
        # Fixed xe reionization model implemented. 
        # First, solve without reionization.

        # tfirst=True means that tla_before_reion accepts rs as 
        # first argument.
        soln_no_reion = odeint(
            tla_before_reion, _init_cond, rs_vec, 
            mxstep = mxstep, tfirst=True
        )
        # soln_no_reion = solve_ivp(
        #     tla_before_reion, (rs_vec[0], rs_vec[-1]),
        #     init_cond, method='BDF', t_eval=rs_vec
        # )
        # Check if reionization model is required in the first place.
        if rs_reion_vec.size == 0:
            soln = soln_no_reion
            # Convert to xe
            soln[:,1] = 0.5 + 0.5*np.tanh(soln[:,1])
        else:
            xe_no_reion = 0.5 + 0.5*np.tanh(soln_no_reion[:,1])
            xe_reion = xe_reion_func(rs_vec)
            # Find where to solve the TLA. Must lie below reion_rs and 
            # have xe_reion > xe_no_reion.
            where_new_soln = (xe_reion > xe_no_reion) & (rs_vec < reion_rs)

            # Find the respective redshift arrays. 
            rs_above_std_xe_vec = rs_vec[where_new_soln]
            rs_below_std_xe_vec = rs_vec[~where_new_soln]
            # Append the last redshift before reionization model. 
            rs_above_std_xe_vec = np.insert(
                rs_above_std_xe_vec, 0, rs_below_std_xe_vec[-1]
            )

            # Define the solution array. Get the entries from soln_no_reion.
            soln = np.zeros_like(soln_no_reion)
            soln[~where_new_soln, :] = soln_no_reion[~where_new_soln, :]
            # Convert to xe.
            soln[~where_new_soln, 1] = 0.5 + 0.5*np.tanh(
                soln[~where_new_soln,1]
            )

            # Solve for all subsequent redshifts. 
            if rs_above_std_xe_vec.size > 0:
                init_cond_fixed_xe = soln[~where_new_soln, 0][-1]
                soln_with_reion = odeint(
                    tla_reion_fixed_xe, init_cond_fixed_xe, 
                    rs_above_std_xe_vec, mxstep=mxstep, tfirst=True
                )
                # Remove the initial step, save to soln.
                soln[where_new_soln, 0] = np.squeeze(soln_with_reion[1:])
                soln[where_new_soln, 1] = xe_reion_func(
                    rs_vec[where_new_soln]
                )

            return soln

    else:
        # Reionization model implemented. 
        # First, check if required in the first place. 
        if rs_reion_vec.size == 0:
            soln = odeint(
                tla_before_reion, _init_cond, 
                rs_before_reion_vec, mxstep = mxstep, tfirst=True
            )
            # soln = solve_ivp(
            #     tla_before_reion, 
            #     (rs_before_reion_vec[0], rs_before_reion_vec[-1]),
            #     init_cond, method='BDF', t_eval=rs_before_reion_vec
            # )
        # Conversely, solving before reionization may be unnecessary.
        elif rs_before_reion_vec.size == 0:
            soln = odeint(
                tla_reion, _init_cond, rs_reion_vec, 
                mxstep = mxstep, tfirst=True
            )
            # soln = solve_ivp(
            #     tla_reion, (rs_reion_vec[0], rs_reion_vec[-1]),
            #     init_cond, method='BDF', t_eval=rs_reion_vec
            # )
        # Remaining case straddles both before and after reionization.
        else:
            # First, solve without reionization up to rs = reion_rs.
            rs_before_reion_vec = np.append(rs_before_reion_vec, reion_rs)
            soln_before_reion = odeint(
                tla_before_reion, _init_cond, 
                rs_before_reion_vec, mxstep = mxstep, tfirst=True, rtol=1e-4
            )
            # soln_before_reion = solve_ivp(
            #     tla_before_reion, 
            #     (rs_before_reion_vec[0], rs_before_reion_vec[-1]),
            #     init_cond, method='BDF', t_eval=rs_before_reion_vec
            # )
            # Next, solve with reionization starting from reion_rs.
            rs_reion_vec = np.insert(rs_reion_vec, 0, reion_rs)
            # Initial conditions taken from last step before reionization.
            init_cond_reion = [
                soln_before_reion[-1,0],
                soln_before_reion[-1,1],
                soln_before_reion[-1,2],
                soln_before_reion[-1,3]
            ]
            print(soln_before_reion)
            print(init_cond_reion)
            soln_reion = odeint(
                tla_reion, init_cond_reion, 
                rs_reion_vec, mxstep = mxstep, tfirst=True, rtol=1e-4
            )
            print(soln_reion)
            # soln_reion = solve_ivp(
            #     tla_reion, (rs_reion_vec[0], rs_reion_vec[-1]),
            #     init_cond, method='BDF', t_eval=rs_reion_vec
            # )
            # Stack the solutions. Remove the solution at 16.1.
            soln = np.vstack((soln_before_reion[:-1,:], soln_reion[1:,:]))

    soln[:,1] = 0.5 + 0.5*np.tanh(soln[:,1])
    soln[:,2] = (
        chi/2 + chi/2*np.tanh(soln[:,2])
    )
    soln[:,3] = (
        chi/2 + chi/2*np.tanh(soln[:,3])
    )

    return soln
