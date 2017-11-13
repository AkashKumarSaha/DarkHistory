""" Non-physics functions used in darkhistory.

"""

import numpy as np

def arrays_equal(ndarray_list):
    """Check if the arrays contained in `ndarray_list` are equal.
        
    Parameters
    ----------
    ndarray_list : sequence of ndarrays
        List of arrays to compare.
    
    Returns
    -------
        bool
            True if equal, False otherwise.

    """

    same = True
    ind = 0
    while same and ind < len(ndarray_list) - 1:
        same = same & np.array_equal(ndarray_list[ind], 
            ndarray_list[ind+1])
        ind += 1
    return same

def is_log_spaced(arr):
    """Checks if `arr` is a log-spaced array.
        
    Parameters
    ----------
    arr : ndarray
        Array for checking.
    
    Returns
    -------
        bool
            True if equal, False otherwise.

    """
    return not bool(np.ptp(np.diff(np.log(arr))))

def compare_arr(ndarray_list):
    """ Prints the arrays in a suitable format for comparison.

    Parameters
    ----------
    ndarray_list : list of ndarray
        The list of 1D arrays to compare.
    """

    print(np.stack(ndarray_list, axis=-1))

    return 0

def log_1_plus_x(x):
    """ Computes log(1+x) with greater floating point accuracy. 

    Unlike scipy.special.log1p, this can take float128. However the performance is certainly slower. See "What every computer scientist should know about floating-point arithmetic" by David Goldberg for details. If that trick does not work, the code reverts to a Taylor expansion.

    Parameters
    ----------
    x : ndarray
        The input value. 

    Returns
    -------
    ndarray
        log(1+x). 
    """
    ind_not_zero = ((1+x) - 1 != 0)
    expr = np.zeros_like(x)

    if np.any(ind_not_zero):
        expr[ind_not_zero] = (
            x[ind_not_zero]*np.log(1+x[ind_not_zero])
            /((1+x[ind_not_zero]) - 1)
        )

    if np.any(~ind_not_zero):
        expr[~ind_not_zero] = (
            x[~ind_not_zero] - x[~ind_not_zero]**2/2 
            + x[~ind_not_zero]**3/3
            - x[~ind_not_zero]**4/4 + x[~ind_not_zero]**5/5
            - x[~ind_not_zero]**6/6 + x[~ind_not_zero]**7/7
            - x[~ind_not_zero]**8/8 + x[~ind_not_zero]**9/9
            - x[~ind_not_zero]**10/10 + x[~ind_not_zero]**11/11
        )
    return expr

def bernoulli(k):
    """ Returns the kth Bernoulli number. 

    This function is written as a look-up table for the first few Bernoulli numbers for speed. 

    Parameters
    ----------
    k : int
        The Bernoulli number to return. 

    Returns
    -------
    float
        The kth Bernoulli number.
    """

    import scipy.special as sp

    B_n = np.array([1, -1/2, 1/6, 0, -1/30,
        0, 1/42, 0, -1/30, 0, 5/66, 
        0, -691/2730, 0, 7/6, 0, -3617/510, 
        0, 43867/798, 0, -174611/330, 0, 854513/138
    ])

    if k <= 22:
        return B_n[k]
    else:
        return sp.bernoulli(k)[-1]

def log_series_diff(b, a):
    """ Returns the Taylor series for log(1+b) - log(1+a). 

    Parameters
    ----------
    a : ndarray
        Input for log(1+a). 
    b : ndarray
        Input for log(1+b). 

    Returns
    -------
    ndarray
        The Taylor series log(1+b) - log(1+a), up to the 11th order term. 

    """
    return(
        - (b-a) - (b**2 - a**2)/2 - (b**3 - a**3)/3
        - (b**4 - a**4)/4 - (b**5 - a**5)/5 - (b**6 - a**6)/6
        - (b**7 - a**7)/7 - (b**8 - a**8)/8 - (b**9 - a**9)/9
        - (b**10 - a**10)/10 - (b**11 - a**11)/11
    )

def spence_series_diff(b, a):
    """ Returns the Taylor series for Li2(b) - Li2(a). 

    Parameters
    ----------
    a : ndarray
        Input for Li2(a). 
    b : ndarray
        Input for Li2(b). 

    Returns
    -------
    ndarray
        The Taylor series Li2(b) - Li2(a), up to the 11th order term. 

    """

    return(
        (b - a) + (b**2 - a**2)/2**2 + (b**3 - a**3)/3**2
        + (b**4 - a**4)/4**2 + (b**5 - a**5)/5**2
        + (b**6 - a**6)/6**2 + (b**7 - a**7)/7**2
        + (b**8 - a**8)/8**2 + (b**9 - a**9)/9**2
        + (b**10 - a**10)/10**2 + (b**11 - a**11)/11**1
    )

def exp_expn(n, x):
    """ Returns exp(x)*E_n(n, x). 

    Circumvents overflow error in np.exp by expanding the exponential integral in a series. 
    
    Parameters
    ----------
    n : {1,2}
        The order of the exponential integral. 
    x : ndarray
        The argument of the function. 

    Returns
    -------
    ndarray
        The result of exp(x)*E_n(n, x)

    """
    import scipy.special as sp

    x_flt64 = np.array(x, dtype='float64')

    low = x < 700
    high = ~low
    expr = np.zeros_like(x)

    if np.any(low):
        expr[low] = np.exp(x[low])*sp.expn(n, x_flt64[low])
    if np.any(high):
        if n == 1:
            # The relative error is roughly 1e-15 for 700, smaller for larger arguments. 
            expr[high] = (
                1/x[high] - 1/x[high]**2 + 2/x[high]**3 - 6/x[high]**4
                + 24/x[high]**5
            )
        elif n == 2:
            # The relative error is roughly 6e-17 for 700, smaller for larger arguments. 
            expr[high] = (
                1/x[high] - 2/x[high]**2 + 6/x[high]**3 - 24/x[high]**4
                + 120/x[high]**5 - 720/x[high]**6
            )
        else:
            raise TypeError('only supports n = 1 or 2 for x > 700.')

    return expr

def check_err(val, err, epsrel):
    """ Checks the relative error given a tolerance.
    
    Parameters
    ----------
    val : float or ndarray
        The computed value. 
    err : float or ndarray
        The computed error. 
    epsrel : float
        The target tolerance. 

    """
    if np.max(np.abs(err/val)) > epsrel:
        print('Series relative error is: ', err/val)
        print('Relative error required is: ', epsrel)
        raise RuntimeError('Relative error in series too large.')
        
    return None
