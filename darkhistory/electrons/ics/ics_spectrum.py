"""Nonrelativistic ICS spectrum after integrating over CMB."""

import numpy as np 
from scipy.integrate import quad

from darkhistory.electrons.ics.bose_einstein_integrals import *
from darkhistory.electrons.ics.nonrel_diff_terms import *
from darkhistory.utilities import log_1_plus_x
from darkhistory import physics as phys
from darkhistory.spec.spectrum import Spectrum
from darkhistory.spec.transferfunction import TransFuncAtRedshift


from tqdm import tqdm_notebook as tqdm

def nonrel_spec_series(
    eleckineng, photeng, T, as_pairs=False, spec_type='new'
):
    """ Nonrelativistic ICS spectrum of secondary photons by series method.

    Parameters
    ----------
    eleckineng : ndarray
        Incoming electron kinetic energy. 
    photeng : ndarray
        Outgoing photon energy. 
    T : float
        CMB temperature. 
    as_pairs : bool
        If true, treats eleckineng and photeng as a paired list: produces eleckineng.size == photeng.size values. Otherwise, gets the spectrum at each photeng for each eleckineng, returning an array of length eleckineng.size*photeng.size. 
    spec_type : {'old', 'new'}
        Choice of secondary photon spectrum to use.

    Returns
    -------
    ndarray
        dN/(dt dE) of the outgoing photons (dt = 1 s), with abscissa photeng. 

    Note
    ----
    Insert note on the suitability of the method. 
    """

    print('Computing spectra by analytic series...')

    gamma = 1 + eleckineng/phys.me
    # Most accurate way of finding beta when beta is small, I think.
    beta = np.sqrt(eleckineng/phys.me*(gamma+1)/gamma**2)

    if as_pairs:
        lowlim = (1-beta)/(1+beta)*photeng/T 
        upplim = (1+beta)/(1-beta)*photeng/T
    else: 
        lowlim = np.outer((1-beta)/(1+beta), photeng/T)
        upplim = np.outer((1+beta)/(1-beta), photeng/T)
    
    eta = photeng/T

    if spec_type == 'old':
        prefac = np.float128( 
            phys.c*(3/8)*phys.thomson_xsec/(2*gamma**3*beta**2)
            * (8*np.pi/(phys.ele_compton*phys.me)**3) 
            * (1+beta**2)/beta**2*np.sqrt((1+beta)/(1-beta))
        )
    elif spec_type == 'new':
        prefac = np.float128(
            phys.c*(3/8)*phys.thomson_xsec/(4*gamma**2*beta**6)
            * (8*np.pi*T**2/(phys.ele_compton*phys.me)**3)
        )

    else:
        raise TypeError('invalid spec specified.')

    print('*** Computing series 1/12...')
    F1_low = F1(lowlim, eta)
    print('*** Computing series 2/12...')
    F0_low = F0(lowlim, eta)
    print('*** Computing series 3/12...')
    F_inv_low = F_inv(lowlim, eta)[0]
    print('*** Computing series 4/12...')
    F_log_low = F_log(lowlim, eta)[0]

    print('*** Computing series 5/12...')
    F1_upp = F1(eta, upplim)
    print('*** Computing series 6/12...')
    F0_upp = F0(eta, upplim)
    print('*** Computing series 7/12...')
    F_inv_upp = F_inv(eta, upplim)[0]
    print('*** Computing series 8/12...')
    F_log_upp = F_log(eta, upplim)[0]

    if spec_type == 'new':
        F2_low = F2(lowlim, eta)[0]
        print('*** Computing series 9/12...')
        F2_upp = F2(eta, upplim)[0]
        print('*** Computing series 10/12...')
        F_x_log_low = F_x_log(lowlim, eta)[0]
        print('*** Computing series 11/12...')
        F_x_log_upp = F_x_log(eta, upplim)[0]
        print('*** Computing series 12/12...')


    # CMB photon energy less than outgoing photon energy.

    # F1_low an array of size [eleckineng, photeng]. 
    # We can take photeng*F1_vec_low for element-wise products. 
    # In the other dimension, we must take transpose(eleckineng*transpose(x)).

    if spec_type == 'old':

        # CMB photon energy lower than outgoing photon energy

        term_low_1 = F1_low * T**2

        term_low_2 = np.transpose(
            2*beta/(1+beta**2)*(1-beta)/(1+beta)
            * np.transpose(photeng*F0_low) * T
        )

        term_low_3 = np.transpose(
            -(1-beta)**2/(1+beta**2)
            * np.transpose((photeng**2)*F_inv_low)
        )

        term_low_4 = np.transpose(
            2*(1-beta)/(1+beta**2)*(log_1_plus_x(-beta) - log_1_plus_x(beta))
            * np.transpose(photeng*F0_low*T)
            + 2*(1-beta)/(1+beta**2) 
            * np.transpose(np.log(photeng)*photeng*F0_low*T)
        )

        term_low_5 = np.transpose(
            -2*(1-beta)/(1+beta**2) * np.transpose(
                photeng*(T*np.log(T)*F0_low + F_log_low*T)
            )
        )

        # CMB photon energy higher than outgoing photon energy

        term_high_1 = np.transpose(
            -(1-beta)/(1+beta) * np.transpose(F1_upp * T**2)
        )

        term_high_2 = np.transpose(
            2*beta/(1+beta**2) * np.transpose(photeng * F0_upp * T)
        )

        term_high_3 = np.transpose(
            (1-beta**2)/(1+beta**2) * np.transpose(photeng**2*F_inv_upp)
        )

        term_high_4 = np.transpose(
            - 2*(1-beta)/(1+beta**2)*(log_1_plus_x(beta) - log_1_plus_x(-beta))
            * np.transpose(photeng*F0_upp*T)
            - 2*(1-beta)/(1+beta**2) 
            * np.transpose(np.log(photeng)*photeng*F0_upp*T)
        )

        term_high_5 = np.transpose(
            2*(1-beta)/(1+beta**2) * np.transpose(
                photeng*(T*np.log(T)*F0_upp+ F_log_upp*T)
            )
        )

    elif spec_type == 'new':

        # CMB photon energy lower than outgoing photon energy

        term_low_1 = np.transpose(
            -(1/gamma**4)*np.transpose(
                photeng**2/T**2*F_inv_low
            )
        )

        term_low_2 = np.transpose(
            (
                (1-beta)*(
                    beta*(beta**2 + 3) - (1/gamma**2)*(9 - 4*beta**2)
                )
                - 2/gamma**2*(3-beta**2)
                *(np.log1p(beta)-np.log1p(-beta))
            )*np.transpose(photeng/T*F0_low)
        ) - np.transpose(
            2/gamma**2*(3 - beta**2)*np.transpose(
                photeng/T*(-np.log(photeng/T))*F0_low
            )
        )

        term_low_3 = np.transpose(
            -2/gamma**2*(3 - beta**2)*np.transpose(
                photeng/T*F_log_low
            )
        )

        term_low_4 = np.transpose(
            -(2/gamma**2)*(3 - beta**2)
            *(np.log1p(beta)-np.log1p(-beta))*np.transpose(F1_low)
            +(2/gamma**2)*(3 - beta**2)*np.transpose(
                np.log(photeng/T)*F1_low
            )
            +(1+beta)*(
                beta*(beta**2 + 3) + (1/gamma**2)*(9 - 4*beta**2)
            )*np.transpose(F1_low) 
        )

        term_low_5 = np.transpose(
            1/gamma**4*np.transpose(F2_low/(photeng/T))
        )

        term_low_6 = np.transpose(
            -2/gamma**2*(3 - beta**2)*np.transpose(F_x_log_low)
        )

        # CMB photon energy higher than outgoing photon energy

        term_high_1 = np.transpose(
            (1/gamma**4)*np.transpose(
                photeng**2/T**2*F_inv_upp
            )
        )

        term_high_2 = np.transpose(
            (
                (1+beta)*(
                    beta*(beta**2 + 3) + (1/gamma**2)*(9 - 4*beta**2)
                )
                + (2/gamma**2)*(3-beta**2)
                    *(np.log1p(-beta)-np.log1p(beta))
            )*np.transpose(photeng/T*F0_upp)
        ) + np.transpose(
            2/gamma**2*(3 - beta**2)*np.transpose(
                photeng/T*(-np.log(photeng/T))*F0_upp
            )
        )

        term_high_3 = np.transpose(
            2/gamma**2*(3 - beta**2)*np.transpose(
                photeng/T*F_log_upp
            )
        )

        term_high_4 = np.transpose(
            (2/gamma**2)*(3 - beta**2)
            *(np.log1p(-beta)-np.log1p(beta))*np.transpose(F1_upp)
            +(2/gamma**2)*(3 - beta**2)*np.transpose(
                -np.log(photeng/T)*F1_upp
            )
            +(1-beta)*(
                beta*(beta**2 + 3) - (1/gamma**2)*(9 - 4*beta**2)
            )*np.transpose(F1_upp) 
        )

        term_high_5 = -np.transpose(
            1/gamma**4*np.transpose(F2_upp/(photeng/T))
        )

        term_high_6 = np.transpose(
            2/gamma**2*(3 - beta**2)*np.transpose(F_x_log_upp)
        )

    testing = False
    if testing:
        print('***** Diagnostics *****')
        print('lowlim: ', lowlim)
        print('upplim: ', upplim)
        print('photeng/T: ', eta)
        print('beta: ', beta)

        print('***** epsilon < epsilon_1 *****')
        print('term_low_1: ', term_low_1)
        print('term_low_2: ', term_low_2)
        print('term_low_3: ', term_low_3)
        print('term_low_4: ', term_low_4)
        print('term_low_5: ', term_low_5)
        if spec_type == 'new':
            print('term_low_6: ', term_low_6)

        print('***** epsilon > epsilon_1 *****')
        print('term_high_1: ', term_high_1)
        print('term_high_2: ', term_high_2)
        print('term_high_3: ', term_high_3)
        print('term_high_4: ', term_high_4)
        print('term_high_5: ', term_high_5)
        if spec_type == 'new':
            print('term_high_6: ', term_high_6)

        print('***** Term Sums *****')
        print('term_low_1 + term_high_1: ', term_low_1 + term_high_1)
        print('term_low_2 + term_high_2: ', term_low_2 + term_high_2)
        print('term_low_3 + term_high_3: ', term_low_3 + term_high_3)
        print('term_low_4 + term_high_4: ', term_low_4 + term_high_4)
        print('term_low_5 + term_high_5: ', term_low_5 + term_high_5)
        if spec_type == 'new':
            print(
                'term_low_6 + term_high_6: ', 
                term_low_6 + term_high_6
            )

        print('***** Prefactor *****')
        print(prefac)
        
        print('***** Total Sum *****')
        if spec_type == 'old':
            print(
                np.transpose(
                    prefac*np.transpose(
                        (term_low_1 + term_high_1)
                        + (term_low_2 + term_high_2)
                        + (term_low_3 + term_high_3)
                        + (term_low_4 + term_high_4)
                        + (term_low_5 + term_high_5)
                    )
                )
            )
        elif spec_type == 'new':
            print(
                np.transpose(
                    prefac*np.transpose(
                        (term_low_1 + term_high_1)
                        + (term_low_2 + term_high_2)
                        + (term_low_3 + term_high_3)
                        + (term_low_4 + term_high_4)
                        + (term_low_5 + term_high_5)
                        + (term_low_6 + term_high_6)
                    )
                )
            )
        print('***** End Diagnostics *****')

    # Addition ordered to minimize catastrophic cancellation, but if this is important, you shouldn't be using this method.

    print('----> Computation by analytic series complete!')

    if spec_type == 'old':

        return np.transpose(
            prefac*np.transpose(
                (term_low_1 + term_high_1)
                + (term_low_2 + term_high_2)
                + (term_low_3 + term_high_3)
                + (term_low_4 + term_high_4)
                + (term_low_5 + term_high_5)
            )
        )

    elif spec_type == 'new':
        return np.transpose(
            prefac*np.transpose(
                (term_low_1 + term_high_1)
                + (term_low_2 + term_high_2)
                + (term_low_3 + term_high_3)
                + (term_low_4 + term_high_4)
                + (term_low_5 + term_high_5)
                + (term_low_6 + term_high_6)
            )
        )

def nonrel_spec_quad(eleckineng_arr, photeng_arr, T, spec_type='new'):
    """ Nonrelativistic ICS spectrum of secondary photons using quadrature.

    Parameters
    ----------
    eleckineng : ndarray
        Incoming electron kinetic energy. 
    photeng : ndarray
        Outgoing photon energy. 
    T : float
        CMB temperature. 
    spec_type : {'old', 'new'}
        Choice of secondary photon spectrum to use.

    Returns
    -------
    ndarray
        dN/(dt dE) of the outgoing photons (dt = 1 s), with abscissa photeng. 

    Note
    ----
    Insert note on the suitability of the method. 
    """

    gamma_arr = eleckineng_arr/phys.me + 1

    # Most accurate way of finding beta when beta is small, I think.
    beta_arr = np.sqrt(
        eleckineng_arr/phys.me*(gamma_arr+1)/gamma_arr**2
    )

    lowlim = np.array([(1-b)/(1+b)*photeng_arr for b in beta_arr])
    upplim = np.array([(1+b)/(1-b)*photeng_arr for b in beta_arr])

    def integrand(eps, eleckineng, photeng):

        gamma = eleckineng/phys.me + 1
        beta = np.sqrt(eleckineng/phys.me*(gamma+1)/gamma**2)


        if spec_type == 'old':
            prefac = ( 
                phys.c*(3/8)*phys.thomson_xsec/(2*gamma**3*beta**2)
                * (8*np.pi/(phys.ele_compton*phys.me)**3)
            )
        elif spec_type == 'new':
            prefac = (
                phys.c*(3/8)*phys.thomson_xsec/(4*gamma**2*beta**6)
                * (8*np.pi/(phys.ele_compton*phys.me)**3)
            )
        else:
            raise TypeError('invalid spec specified.')

        if eps/T < 100:
            prefac *= 1/(np.exp(eps/T) - 1)
        else:
            prefac = 0

        if eps < photeng:

            if spec_type == 'old':

                fac = (
                    (1+beta**2)/beta**2*np.sqrt((1+beta)/(1-beta))*eps
                    + 2/beta*np.sqrt((1-beta)/(1+beta))*photeng
                    - (1-beta)**2/beta**2*np.sqrt((1+beta)/(1-beta))*(
                        photeng**2/eps
                    )
                    + 2/(gamma*beta**2)*photeng*np.log(
                        (1-beta)/(1+beta)*photeng/eps
                    )
                )

            else:

                fac = (
                    - (2/gamma**2)*(3-beta**2)*(eps+photeng)*np.log(
                        (1+beta)*eps/((1-beta)*photeng)
                    )
                    + (1/gamma**4)*(eps**2/photeng)
                    - (1/gamma**4)*(photeng**2/eps)
                    +(1+beta)*(
                        beta*(beta**2+3) + (1/gamma**2)*(9-4*beta**2) 
                    )*eps
                    + (1-beta)*(
                        beta*(beta**2+3) - (1/gamma**2)*(9-4*beta**2)
                    )*photeng
                )


        else:

            if spec_type == 'old':

                fac = (
                    - (1+beta**2)/beta**2*np.sqrt((1-beta)/(1+beta))*eps
                    + 2/beta*np.sqrt((1+beta)/(1-beta))*photeng 
                    + (1+beta)/(gamma*beta**2)*photeng**2/eps 
                    - 2/(gamma*beta**2)*photeng*np.log(
                        (1+beta)/(1-beta)*photeng/eps 
                    )
                )

            else:

                fac = (
                    (2/gamma**2)*(3-beta**2)*(eps+photeng)*np.log(
                        (1-beta)*eps/((1+beta)*photeng)
                    )
                    - (1/gamma**4)*(eps**2/photeng)
                    + (1/gamma**4)*(photeng**2/eps)
                    -(1-beta)*(
                        -beta*(beta**2+3) + (1/gamma**2)*(9-4*beta**2) 
                    )*eps
                    -(1+beta)*(
                        -beta*(beta**2+3) - (1/gamma**2)*(9-4*beta**2)
                    )*photeng
                )

        return prefac*fac

    integral = np.array([
        [quad(integrand, low, upp, args=(eleckineng, photeng), epsabs=0)[0] 
        for (low, upp, photeng) in zip(low_part, upp_part, photeng_arr)
        ] for (low_part, upp_part, eleckineng) 
            in zip(tqdm(lowlim), upplim, eleckineng_arr)
    ]) 

    testing = False
    if testing:
        print('***** Diagnostics *****')
        print('***** Integral (Excluding Prefactor) *****')
        prefac = ( 
            phys.c*(3/8)*phys.thomson_xsec/(2*gamma_arr**3*beta_arr**2)
            * (8*np.pi/(phys.ele_compton*phys.me)**3) 
        )
        print(np.transpose(np.transpose(integral)/prefac))
        print('***** Integration with Error *****')
        print(np.array([
            [
                quad(
                    integrand, low, upp, 
                    args=(eleckineng, photeng), 
                    epsabs = 0, epsrel=1e-10
                )
                for (low, upp, photeng) in zip(
                    low_part, upp_part, photeng_arr
                )
            ] for (low_part, upp_part, eleckineng) 
                in zip(lowlim, upplim, eleckineng_arr)
        ]))
        print('***** End Diagnostics *****')


    return integral

def nonrel_spec_diff(eleckineng, photeng, T, as_pairs=False, spec_type='new'):
    """ Nonrelativistic ICS spectrum of secondary photons by beta expansion.

    Parameters
    ----------
    eleckineng : ndarray
        Incoming electron kinetic energy. 
    photeng : ndarray
        Outgoing photon energy. 
    T : float
        CMB temperature.
    as_pairs : bool
        If true, treats eleckineng and photeng as a paired list: produces eleckineng.size == photeng.size values. Otherwise, gets the spectrum at each photeng for each eleckineng, returning an array of length eleckineng.size*photeng.size.
    spec_type : {'old', 'new'}
        Choice of secondary photon spectrum to use. 

    Returns
    -------
    tuple of ndarrays
        dN/(dt dE) of the outgoing photons (dt = 1 s) and the error, with abscissa given by (eleckineng, photeng). 

    Note
    ----
    Insert note on the suitability of the method. 
    """

    print('Computing spectra by an expansion in beta...')

    gamma = eleckineng/phys.me + 1
    # Most accurate way of finding beta when beta is small, I think.
    beta = np.sqrt(eleckineng/phys.me*(gamma+1)/gamma**2)

    testing = False
    if testing: 
        print('beta: ', beta)

    if spec_type == 'old':
        prefac = ( 
            phys.c*(3/8)*phys.thomson_xsec/(2*gamma**3*beta**2)
            * (8*np.pi/(phys.ele_compton*phys.me)**3)
        )
    elif spec_type == 'new':
        # The terms dependent on beta have been absorbed into
        # the expansion.
        prefac = (
            phys.c*(3/8)*phys.thomson_xsec/4
            * (
                8*np.pi*T**2
                /(phys.ele_compton*phys.me)**3
            )
        )
    else:
        raise TypeError('invalid spec specified.')

    if spec_type == 'old':

        print('Computing Q and K terms...')
        Q_and_K_term = Q_and_K(beta, photeng, T, as_pairs=as_pairs)
        print('Computing H and G terms...')
        H_and_G_term = H_and_G(beta, photeng, T, as_pairs=as_pairs)

    elif spec_type == 'new':

        diff_term = diff_expansion(beta, photeng, T, as_pairs=as_pairs)

    if spec_type == 'old':
        term = np.transpose(
            prefac*np.transpose(
                Q_and_K_term[0] + H_and_G_term[0]
            )
        )

        err = np.transpose(
            prefac*np.transpose(
                Q_and_K_term[1] + H_and_G_term[1]
            )
        )

    elif spec_type == 'new':
        # print('Prefactor: ', prefac)
        # print('Sum without prefac: ', diff_term[0])
        term = np.transpose(prefac*np.transpose(diff_term[0]))

        err = np.transpose(prefac*np.transpose(diff_term[1]))

    print('----> Computation by expansion in beta complete!')

    return term, err

def nonrel_spec(eleckineng, photeng, T, as_pairs=False, spec_type='new'):
    """ Nonrelativistic ICS spectrum of secondary photons.

    Switches between `nonrel_spec_diff` and `nonrel_spec_series`. 

    Parameters
    ----------
    eleckineng : ndarray
        Incoming electron kinetic energy. 
    photeng : ndarray
        Outgoing photon energy. 
    T : float
        CMB temperature. 
    as_pairs : bool
        If true, treats eleckineng and photeng as a paired list: produces eleckineng.size == photeng.size values. Otherwise, gets the spectrum at each photeng for each eleckineng, returning an array of length eleckineng.size*photeng.size.
    spec_type : {'old', 'new'}
        Choice of secondary photon spectrum to use.

    Returns
    -------
    TransFuncAtRedshift or ndarray
        dN/(dt dE) of the outgoing photons (dt = 1 s). If as_pairs == False, returns a TransFuncAtRedshift, with abscissa given by (eleckineng, photeng). Otherwise, returns an ndarray, with abscissa given by each pair of (eleckineng, photeng).  

    Note
    ----
    Insert note on the suitability of the method. 
    """

    print('Initializing...')

    gamma = eleckineng/phys.me + 1
    # Most accurate way of finding beta when beta is small, I think.
    beta = np.sqrt(eleckineng/phys.me*(gamma+1)/gamma**2)
    eta = photeng/T 

    # Masks, dimensions (eleckineng, photeng) if as_pairs == False.
    if as_pairs:
        if eleckineng.size != photeng.size:
            raise TypeError('Photon and electron energy arrays must have the same length for pairwise computation.')
        beta_mask = beta
        eta_mask = eta
        eleckineng_mask = eleckineng
        photeng_mask = photeng
    else:
        beta_mask = np.outer(beta, np.ones(eta.size))
        eta_mask = np.outer(np.ones(beta.size), eta)
        eleckineng_mask = np.outer(eleckineng, np.ones(photeng.size))
        photeng_mask = np.outer(np.ones(eleckineng.size), photeng)

    # Boolean arrays. Depending on as_pairs, can be 1- or 2-D. 
    beta_small = (beta_mask < 0.01)
    eta_small  = (eta_mask < 0.1/beta_mask)

    where_diff = (beta_small & eta_small)

    testing = False

    if testing:
        print('where_diff on (eleckineng, photeng) grid: ')
        print(where_diff)

    if as_pairs:
        spec = np.zeros_like(eleckineng)
        epsrel = np.zeros_like(eleckineng)
    else:
        spec = np.zeros((eleckineng.size, photeng.size), dtype='float128')
        epsrel = np.zeros((eleckineng.size, photeng.size), dtype='float128')

    spec[where_diff], err_with_diff = nonrel_spec_diff(
        eleckineng_mask[where_diff], 
        photeng_mask[where_diff], 
        T, as_pairs=True, spec_type=spec_type
    )

    epsrel[where_diff] = np.abs(
        np.divide(
            err_with_diff,
            spec[where_diff],
            out = np.zeros_like(err_with_diff),
            where = (spec[where_diff] != 0)
        )
    )
    
    if testing:
        print('spec from nonrel_spec_diff: ')
        print(spec)
        print('epsrel from nonrel_spec_diff: ')
        print(epsrel)

    where_series = (~where_diff) | (epsrel > 1e-3)

    if testing:
    
        print('where_series on (eleckineng, photeng) grid: ')
        print(where_series)

    spec[where_series] = nonrel_spec_series(
        eleckineng_mask[where_series],
        photeng_mask[where_series],
        T, as_pairs=True, spec_type=spec_type
    )

    if testing:
        spec_with_series = np.array(spec)
        spec_with_series[~where_series] = 0
        print('spec from nonrel_spec_series: ')
        print(spec_with_series)
        print('*********************')
        print('Final Result: ')
        print(spec)

    print('Spectrum computed!')

    # Zero out spec values that are too small (clearly no scatters within the age of the universe), and numerical errors. Non-zero so that we can take log interpolations later.
    spec[spec < 1e-100] = 0.

    if as_pairs:
        return spec
    else:
        rs = T/phys.TCMB(1)
        dlnz = 1/(phys.dtdz(rs)*rs)

        spec_arr = [
            Spectrum(photeng, s, rs=rs, in_eng=in_eng) 
            for s, in_eng in zip(spec, eleckineng)
        ]

        # Injection energy is kinetic energy of the electron.
        spec_tf = TransFuncAtRedshift(
            spec_arr, dlnz=dlnz, 
            in_eng = eleckineng, eng = photeng,
            with_interp_func = True
        )

        return spec_tf

def rel_spec(eleceng, photeng, T, inf_upp_bound=False, as_pairs=False):
    """ Relativistic ICS spectrum of secondary photons.

    Parameters
    ----------
    eleceng : ndarray
        Incoming electron energy. 
    photeng : ndarray
        Outgoing photon energy. 
    T : float
        CMB temperature. 
    as_pairs : bool
        If true, treats eleceng and photeng as a paired list: produces eleceng.size == photeng.size values. Otherwise, gets the spectrum at each photeng for each eleceng, returning an array of length eleceng.size*photeng.size. 


    Returns
    -------
    TransFuncAtRedshift or ndarray
        dN/(dt dE) of the outgoing photons (dt = 1 s). If as_pairs == False, returns a TransFuncAtRedshift, with abscissa given by (eleceng, photeng). Otherwise, returns an ndarray, with abscissa given by each pair of (eleceng, photeng). 

    Note
    ----
    This function accepts the *energy* of the electron as one of the arguments and not the kinetic energy, unlike the other related ICS functions. This enables the evaluation of the relativistic rate at unphysical values of the electron energy, a mathematical trick that we use when we obtain the ICS rates at a low temperature by interpolating over the result at a higher temperature.

    """
    print('Initializing...')

    gamma = eleceng/phys.me

    if as_pairs:
        if eleceng.size != photeng.size:
            raise TypeError('Photon and electron energy arrays must have the same length for pairwise computation.')
        Gamma_eps_q = (
            np.divide(
                photeng/eleceng,
                1 - photeng/eleceng,
                out = np.zeros_like(photeng),
                where = 1 - photeng/eleceng != 0
            )
        )
        B = phys.me/(4*gamma)*Gamma_eps_q
        lowlim = B/T
        if inf_upp_bound:
            upplim = np.inf*np.ones_like(gamma)
        else:
            upplim = 4*(gamma**2)*B/T
        
    else: 
        photeng_to_eleceng = np.outer(1/eleceng, photeng)
        Gamma_eps_q = (
            np.divide(
                photeng_to_eleceng,
                1 - photeng_to_eleceng,
                out = np.zeros_like(photeng_to_eleceng),
                where = 1 - photeng_to_eleceng != 0
            )
        )
        B = np.transpose(
            phys.me/(4*gamma)*np.transpose(Gamma_eps_q)
        )
        lowlim = B/T
        if inf_upp_bound:
            upplim = np.inf*np.ones_like(photeng_to_eleceng)
        else:
            upplim = np.transpose(
                4*gamma**2*np.transpose(B)/T
            )
        
    spec = np.zeros_like(Gamma_eps_q)
    F1_int = np.zeros_like(Gamma_eps_q)
    F0_int = np.zeros_like(Gamma_eps_q)
    F_inv_int = np.zeros_like(Gamma_eps_q)
    F_log_int = np.zeros_like(Gamma_eps_q)

    term_1 = np.zeros_like(Gamma_eps_q)
    term_2 = np.zeros_like(Gamma_eps_q)
    term_3 = np.zeros_like(Gamma_eps_q)
    term_4 = np.zeros_like(Gamma_eps_q)

    good = (lowlim > 0)

    Q = np.zeros_like(Gamma_eps_q)

    Q[good] = (1/2)*Gamma_eps_q[good]**2/(1 + Gamma_eps_q[good])

    prefac = np.float128( 
        6*np.pi*phys.thomson_xsec*phys.c*T/(gamma**2)
        /(phys.ele_compton*phys.me)**3
    )

    print('Computing series 1/4...')
    F1_int[good] = F1(lowlim[good], upplim[good])
    print('Computing series 2/4...')
    F0_int[good] = F0(lowlim[good], upplim[good])
    print('Computing series 3/4...')
    F_inv_int[good] = F_inv(lowlim[good], upplim[good])[0]
    print('Computing series 4/4...')
    F_log_int[good] = F_log(lowlim[good], upplim[good])[0]

    term_1[good] = (1 + Q[good])*T*F1_int[good]
    term_2[good] = (
        (1 + 2*np.log(B[good]/T) - Q[good])*B[good]*F0_int[good]
    )
    term_3[good] = -2*B[good]*F_log_int[good]
    term_4[good] = -2*B[good]**2/T*F_inv_int[good]
    


    testing = False
    if testing:
        print('***** Diagnostics *****')
        print('gamma: ', gamma)
        print('lowlim: ', lowlim)
        print('lowlim*T: ', lowlim*T)
        print('upplim: ', upplim)
        print('upplim*T: ', upplim*T)
        print('Gamma_eps_q: ', Gamma_eps_q)
        print('Q: ', Q)
        print('B: ', B)

        print('***** Integrals *****')
        print('term_1: ', term_1)
        print('term_2: ', term_2)
        print('term_3: ', term_3)
        print('term_4: ', term_4)
        print('Sum of terms: ', term_1+term_2+term_3+term_4)

        print('Final answer: ', 
            np.transpose(
                prefac*np.transpose(
                    term_1 + term_2 + term_3 + term_4
                )
            )
        )
        
        print('***** End Diagnostics *****')

    print('Relativistic Computation Complete!')

    spec[good] = (
        term_1[good] + term_2[good] + term_3[good] + term_4[good]
    )

    spec = np.transpose(
        prefac*np.transpose(spec)
    )

    # Zero out spec values that are too small (clearly no scatters within the age of the universe), and numerical errors. 
    spec[spec < 1e-100] = 0.

    if as_pairs:
        return spec 
    else:
        rs = T/phys.TCMB(1)
        dlnz = 1/(phys.dtdz(rs)*rs)
        
        spec_arr = [
            Spectrum(photeng, s, rs=rs, in_eng=in_eng) 
            for s, in_eng in zip(spec, eleceng)
        ]

        spec_tf = TransFuncAtRedshift(
            spec_arr, dlnz=dlnz, 
            in_eng = eleceng, eng = photeng,
            with_interp_func = True
        )

        return spec_tf 

def ics_spec(
    eleckineng, photeng, T, as_pairs=False, 
    nonrel_tf=None, rel_tf=None
):
    """ ICS spectrum of secondary photons.

    Switches between `nonrel_spec` and `rel_spec`. 

    Parameters
    ----------
    eleckineng : ndarray
        Incoming electron energy. 
    photeng : ndarray
        Outgoing photon energy. 
    T : float
        CMB temperature. 
    as_pairs : bool, optional
        If true, treats eleckineng and photeng as a paired list: produces eleckineng.size == photeng.size values. Otherwise, gets the spectrum at each photeng for each eleckineng, returning an array of length eleckineng.size*photeng.size. 
    nonrel_tf : TransFuncAtRedshift, optional
        Reference nonrelativistic ICS spectrum. If specified, calculation is done by interpolating over the transfer function. 
    rel_tf : TransFuncAtRedshift, optional
        Reference relativistic ICS spectrum. If specified, calculation is done by interpolating over the transfer function. 

    Returns
    -------
    TransFuncAtRedshift
        dN/(dt dE) of the outgoing photons, dt = 1 s, with `self.in_eng = eleckineng` and `self.eng = photeng`. `self.rs` is determined from `T`, and `self.dlnz` is normalized to 1 second. 

    Note
    ----
    Insert note on the suitability of the method. 
    """

    gamma = eleckineng/phys.me + 1
    eleceng = eleckineng + phys.me

    if as_pairs:
        if eleceng.size != photeng.size:
            raise TypeError('Photon and electron energy arrays must have the same length for pairwise computation.')
        gamma_mask = gamma
        eleceng_mask = eleceng
        eleckineng_mask = eleckineng
        photeng_mask = photeng
        spec = np.zeros(gamma)
    else:
        gamma_mask = np.outer(gamma, np.ones(photeng.size))
        eleceng_mask = np.outer(eleceng, np.ones(photeng.size))
        eleckineng_mask = np.outer(eleckineng, np.ones(photeng.size))
        photeng_mask = np.outer(np.ones(eleceng.size), photeng)
        spec = np.zeros((eleceng.size, photeng.size), dtype='float128')

    rel_bound = 20

    rel = (gamma_mask > rel_bound)

    y = T/phys.TCMB(400)

    if rel_tf != None:
        if as_pairs:
            raise TypeError('When reading from file, the keyword as_pairs is not supported.')
        # If the electron energy at which interpolation is to be taken is outside rel_tf, then an error should be returned, since the file has not gone up to high enough energies. 
        # Note relativistic spectrum is indexed by TOTAL electron energy.
        # rel_tf = rel_tf.at_in_eng(y*eleceng[gamma > rel_bound])
        # If the photon energy at which interpolation is to be taken is outside rel_tf, then for large photon energies, we set it to zero, since the spectrum should already be zero long before. If it is below, nan is returned, and the results should not be used.
        # rel_tf = rel_tf.at_eng(
        #     y*photeng, 
        #     bounds_error = False, 
        #     fill_value = (np.nan, 0)
        # )

        # OLD METHOD: call at_val

        # rel_tf = rel_tf.at_val(
        #     y*eleceng[gamma > rel_bound], y*photeng, 
        #     bounds_error = False, fill_value = 1e-200
        # )
        
        # spec[rel] = y**4*rel_tf.grid_vals.flatten()

        # NEW METHOD: call interpolator. 
        rel_tf_interp = rel_tf.interp_func(
            np.log(y*photeng),
            np.log(y*eleceng[gamma > rel_bound])
        )
        spec[rel] = y**4*rel_tf_interp.flatten()

    else: 
        spec[rel] = rel_spec(
            eleceng_mask[rel], photeng_mask[rel], T, 
            inf_upp_bound=True, as_pairs=True
        )

    if nonrel_tf != None:
        # nonrel_tf = nonrel_tf.at_in_eng(eleckineng[gamma <= rel_bound])
        # nonrel_tf = nonrel_tf.at_eng(
        #     photeng/y,
        #     bounds_error = False,
        #     fill_value = (np.nan, 0)
        # )

        # OLD METHOD: call at_val

        # nonrel_tf = nonrel_tf.at_val(
        #     eleckineng[gamma <= rel_bound], photeng/y, 
        #     bounds_error = False, fill_value = 1e-200
        # )
        # spec[~rel] = y**2*nonrel_tf.grid_vals.flatten()

        # NEW METHOD: call interpolator directly.
        nonrel_tf_interp = nonrel_tf.interp_func(
            np.log(photeng/y),
            np.log(eleckineng[gamma <= rel_bound]) 
        )
        spec[~rel] = y**2*nonrel_tf_interp.flatten()

    else:
        spec[~rel] = nonrel_spec(
            eleckineng_mask[~rel], photeng_mask[~rel], 
            T, as_pairs=True
        )


    # Zero out spec values that are too small (clearly no scatters within the age of the universe), and numerical errors. Non-zero to take log interpolations later.
    spec[spec < 1e-100] = 0.

    if as_pairs:
        return spec
    else:

        rs = T/phys.TCMB(1)
        dlnz = 1/(phys.dtdz(rs)*rs)

        # spec_arr = [
        #     Spectrum(photeng, sp, rs = rs, in_eng = in_eng) 
        #     for sp, in_eng in zip(spec, eleckineng)
        # ]

        # # Use kinetic energy of the electron for better interpolation when necessary. 
        # return TransFuncAtRedshift(spec_arr, dlnz=dlnz)

        return TransFuncAtRedshift(
            spec, in_eng = eleckineng, eng = photeng, 
            rs = np.ones_like(eleckineng)*rs, dlnz=dlnz,
            spec_type = 'dNdE'
        )