import sys
sys.path.append("../..")

import numpy as np
import darkhistory.physics as phys
import darkhistory.spec.spectools as spectools
import time

def get_kappa_2s(photon_spectrum):
    """ Compute kappa_2s for use in kappa_DM function

    Parameters
    ----------
    photon_spectrum : Spectrum object
        spectrum of photons. Assumed to be in dNdE mode. spec.toteng() should return Energy per baryon.

    Returns
    -------
    kappa_2s : float
        The added photoionization rate from the 1s to the 2s state due to DM photons.
    """
    # Convenient Variables
    eng = photon_spectrum.eng
    rs = photon_spectrum.rs
    Lambda = phys.width_2s1s
    Tcmb = phys.TCMB(rs)
    lya_eng = phys.lya_eng

    # Photon phase space density (E >> kB*T approximation)
    def Boltz(E):
        return np.exp(-E/Tcmb)

    bounds = spectools.get_bin_bound(eng)
    mid = spectools.get_indx(bounds, lya_eng/2)

    # Phase Space Density of DM
    f_nu = photon_spectrum.dNdE * phys.c**3 / (
        8 * np.pi * (eng/phys.hbar)**2
    )

    # Complementary (E - h\nu) phase space density of DM
    f_nu_p = np.zeros(mid)

    # Index of point complementary to eng[k]
    comp_indx = spectools.get_indx(bounds, lya_eng - eng[0])

    # Find the bin in which lya_eng - eng[k] resides. Store f_nu of that bin in f_nu_p.
    for k in np.arange(mid):
        while (lya_eng - eng[k]) < bounds[comp_indx]:
            comp_indx -= 1
        f_nu_p[k] = f_nu[comp_indx]

    # Setting up the numerical integration

    # Bin sizes
    diffs = np.append(bounds[1:mid], lya_eng/2) - np.insert(bounds[1:mid], 0, 0)
    diffs /= (2 * np.pi * phys.hbar)

    dLam_dnu = phys.get_dLam2s_dnu()
    rates = dLam_dnu(eng[:mid]/(2 * np.pi * phys.hbar))

    boltz = Boltz(eng[:mid])
    boltz_p = Boltz(lya_eng - eng[:mid])

    # The Numerical Integral
    kappa_2s = np.sum(
        diffs * rates * (f_nu[:mid] + boltz) * (f_nu_p + boltz_p)
    )/phys.width_2s1s - Boltz(lya_eng)

    return kappa_2s

def kappa_DM(photon_spectrum, xe):
    """ Compute kappa_DM of the modified tla.

    Parameters
    ----------
    photon_spectrum : Spectrum object
        spectrum of photons. Assumed to be in dNdE mode. spec.toteng() should return Energy per baryon.

    Returns
    -------
    kappa_DM : float
        The added photoionization rate due to products of DM.
    """
    eng = photon_spectrum.eng
    rs = photon_spectrum.rs
    x1s_times_R_Lya = phys.rate_2p1s_times_x1s(xe,rs)
    Lambda = phys.width_2s1s

    # The bin number containing 10.2eV
    lya_index = spectools.get_indx(eng, phys.lya_eng)

    # The bins between 10.2eV and 13.6eV
    exc_bounds = spectools.get_bounds_between(
        eng, phys.lya_eng, phys.rydberg
    )

    # Convenient variables
    rs = photon_spectrum.rs
    Lambda = phys.width_2s1s

    # Effect on 2p state due to DM products
    kappa_2p = (
        photon_spectrum.dNdE[lya_index] * phys.nB * rs**3 *
        np.pi**2 * (phys.hbar * phys.c)**3 / phys.lya_eng**2
    )

    # Effect on 2s state
    kappa_2s = get_kappa_2s(photon_spectrum)

    return (
        kappa_2p*3*x1s_times_R_Lya/4 + kappa_2s*(1-xe)*Lambda/4
    )/(3*x1s_times_R_Lya/4 + (1-xe)*Lambda/4)

def compute_fs(photon_spectrum, x, dE_dVdt_inj, time_step, method='old'):
    """ Compute f(z) fractions for continuum photons, photoexcitation of HI, and photoionization of HI, HeI, HeII

    Given a spectrum of deposited photons, resolve its energy into continuum photons,
    HI excitation, and HI, HeI, HeII ionization in that order.

    Parameters
    ----------
    photon_spectrum : Spectrum object
        spectrum of photons. Assumed to be in dNdE mode. spec.toteng() should return energy per baryon per time.
    x : list of floats
        number of (HI, HeI, HeII) divided by nH at redshift photon_spectrum.rs
    dE_dVdt_inj : float
        energy injection rate DM, dE/dVdt |_inj
    method : {'old','ion','new'}
        'old': All photons >= 13.6eV ionize hydrogen, within [10.2, 13.6)eV excite hydrogen, < 10.2eV are labelled continuum.
        'ion': Same as 'old', but now photons >= 13.6 can ionize HeI and HeII also.
        'new': Same as 'ion', but now [10.2, 13.6)eV photons treated more carefully.

    Returns
    -------
    tuple of floats
        Ratio of deposited energy to a given channel over energy deposited by DM.
        The order of the channels is {continuum photons, HI excitation, HI ionization, HeI ion, HeII ion}
    """
    #t0 = time.time()
    #print('Begin lowE_photon timing: ',time.time()-t0)
    f_continuum, f_excite_HI, f_HI, f_HeI, f_HeII = 0,0,0,0,0

    eng = photon_spectrum.eng
    rs = photon_spectrum.rs

    chi = phys.nHe/phys.nH
    xHeIII = chi - x[1] - x[2]
    xHII = 1 - x[0]
    xe = xHII + x[2] + 2*xHeIII
    n = x * phys.nH * rs**3

    # norm_factor converts from total deposited energy to f_c(z) = (dE/dVdt)dep / (dE/dVdt)inj
    norm_factor = phys.nB * rs**3 / time_step / dE_dVdt_inj

    # All photons below 10.2eV get deposited into the continuum
    f_continuum = photon_spectrum.toteng(
        bound_type='eng',
        bound_arr=np.array([eng[0],phys.lya_eng])
    )[0] * norm_factor

    #----- Treatment of photoexcitation -----#

    # The bin number containing 10.2eV
    lya_index = spectools.get_indx(eng, phys.lya_eng)
    # The bin number containing 13.6eV
    ryd_index = spectools.get_indx(eng, phys.rydberg)

    #print('Begin photoexcitation: ', time.time()-t0)
    if(method != 'new'):
        # All photons between 10.2eV and 13.6eV are deposited into excitation
        tot_excite_eng = (
            photon_spectrum.toteng(
                bound_type='eng',
                bound_arr=np.array([phys.lya_eng,phys.rydberg])
            )[0]
        )
        f_excite_HI = tot_excite_eng * norm_factor
    else:
        # Only photons in the 10.2eV bin participate in 1s->2p excitation.
        # 1s->2s transition handled more carefully.

        # Convenient variables
        kappa = kappa_DM(photon_spectrum, xe)

        f_excite_HI = (
            kappa * (3*phys.rate_2p1s_times_x1s(xe,rs)*phys.nH + phys.width_2s1s*n[0]) *
            phys.lya_eng / tot_inj
        )


    #----- Treatment of photoionization -----#

    # Bin boundaries of photon spectrum capable of photoionization, and number of photons in those bounds.
    ion_bounds = spectools.get_bounds_between(eng, phys.rydberg)
    ion_Ns = photon_spectrum.totN(bound_type='eng', bound_arr=ion_bounds)

    #print('Begin photoionization: ', time.time()-t0)
    if method == 'old':
        # All photons above 13.6 eV deposit their 13.6eV into HI ionization
        tot_ion_eng = phys.rydberg * sum(ion_Ns)
        f_HI = tot_ion_eng * norm_factor
    else:
        # Photons may also deposit their energy into HeI and HeII single ionization

        # Probability of being absorbed within time step dt in channel a is P_a = \sigma(E)_a n_a c*dt
        ionHI, ionHeI, ionHeII = [phys.photo_ion_xsec(eng[ryd_index:],channel) * n[i]
                                  for i,channel in enumerate(['H0','He0','He1'])]

        # The first energy might be less than 13.6, meaning no photo-ionization.
        # The photons in this box are hopefully all between 13.6 and 24.6, so they can only ionize H
        if eng[ryd_index] < phys.rydberg:
            ionHI[0] = 1

        # Relative likelihood of photoionization of HI is then P_HI/sum(P_a)
        totList = ionHI + ionHeI + ionHeII + 1e-12
        ionHI, ionHeI, ionHeII = [ llist/totList for llist in [ionHI, ionHeI, ionHeII] ]

        f_HI, f_HeI, f_HeII = [
            sum(ion_Ns * llist * norm_factor)
            for llist in [phys.rydberg*ionHI, phys.He_ion_eng*ionHeI, 4*phys.rydberg*ionHeII]
        ]

    #print('Finish: ', time.time()-t0)
    return np.array([f_continuum, f_excite_HI, f_HI, f_HeI, f_HeII])
