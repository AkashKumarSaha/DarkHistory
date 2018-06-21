"""Contains the `Spectra` class."""

import numpy as np
from darkhistory import utilities as utils
from darkhistory.spec.spectools import get_log_bin_width
from darkhistory.spec.spectools import rebin_N_arr
from darkhistory.spec.spectrum import Spectrum

import matplotlib.pyplot as plt
import warnings

from scipy import interpolate

class Spectra:
    """Structure for a collection of `Spectrum` objects. 

    Parameters
    ----------
    spec_arr : list of Spectrum
        List of `Spectrum` to be stored together. 
    spec_type : {'N', 'dNdE'}, optional
        The type of entries. Default is 'dNdE'.
    rebin_eng : ndarray, optional
        New abscissa to rebin all of the spectra into. 

    Attributes
    ----------
    in_eng : ndarray
        Array of injection energies corresponding to each spectrum. 
    eng : ndarray
        Array of energy abscissa of each spectrum. 
    rs : ndarray
        Array of redshifts corresponding to each spectrum. 
    spec_type : {'N', 'dNdE'}
        The type of values stored.
    """

    # __array_priority__ must be larger than 0, so that radd can work.
    # Otherwise, ndarray + Spectrum works by iterating over the elements of
    # ndarray first, which isn't what we want.

    __array_priority__ = 1

    def __init__(
        self, spec_arr, eng=None, in_eng=None, rs=None, 
        spec_type='dNdE', rebin_eng=None
    ):

        if isinstance(spec_arr, np.ndarray):
            if eng is None:
                raise TypeError('Must specify eng to initialize Spectra using an ndarray.')
            if in_eng is None and rs is None:
                raise TypeError('Must specify either eng or rs to initialize Spectra using an ndarray.')

            self._grid_vals = np.atleast_2d(spec_arr)
            self._spec_type = spec_type
            self._eng = eng
            if in_eng is None:
                self._rs = rs
                self._in_eng = -1.*np.ones_like(rs)
                self._N_underflow = np.zeros_like(rs)
                self._eng_underflow = np.zeros_like(rs)
            elif rs is None:
                self._in_eng = in_eng
                self._rs = -1.*np.ones_like(in_eng)
                self._N_underflow = np.zeros_like(in_eng)
                self._eng_underflow = np.zeros_like(in_eng)

            if rebin_eng is not None:
                self.rebin(rebin_eng)

        elif spec_arr != []:

            if len(set([spec.spec_type for spec in spec_arr])) != 1:
                raise TypeError(
                    "all Spectrum must have spec_type 'N' or 'dNdE'."
                )

            if not utils.arrays_equal([spec.eng for spec in spec_arr]):
                raise TypeError("all abscissae must be the same.")

            self._grid_vals = np.atleast_2d(
                np.stack([spec._data for spec in spec_arr])
            )
            self._spec_type = spec_arr[0].spec_type
            self._eng = spec_arr[0].eng
            self._in_eng = np.array([spec.in_eng for spec in spec_arr])
            self._rs = np.array([spec.rs for spec in spec_arr])
            self._N_underflow = np.array(
                [spec.underflow['N'] for spec in spec_arr]
            )
            self._eng_underflow = np.array(
                [spec.underflow['eng'] for spec in spec_arr]
            )

            if rebin_eng is not None:
                self.rebin(rebin_eng)

        else:

            self._grid_vals = np.atleast_2d([])
            self._spec_type = spec_type
            self._eng = np.array([])
            self._in_eng = np.array([])
            self._rs = np.array([])
            self._N_underflow = np.array([])
            self._eng_underflow = np.array([])

    @property
    def eng(self):
        return self._eng

    @property
    def in_eng(self):
        return self._in_eng

    @property
    def rs(self):
        return self._rs

    @property
    def grid_vals(self):
        return self._grid_vals

    @property
    def spec_type(self):
        return self._spec_type

    @property
    def N_underflow(self):
        return self._N_underflow

    @property
    def eng_underflow(self):
        return self._eng_underflow

    def __iter__(self):
        return iter(self.grid_vals)

    def __getitem__(self, key):
        if np.issubdtype(type(key), np.int64):
            out_spec = Spectrum(
                self.eng, self._grid_vals[key], 
                in_eng=self._in_eng[key], rs=self._rs[key], 
                spec_type=self.spec_type
            )
            if self.N_underflow.size > 0 and self.eng_underflow.size > 0:
                out_spec.underflow['N']   = self.N_underflow[key]
                out_spec.underflow['eng'] = self.eng_underflow[key]
            return out_spec
        elif isinstance(key, slice):
            data_arr          = self._grid_vals[key]
            in_eng_arr        = self._in_eng[key]
            rs_arr            = self._rs[key]
            N_underflow_arr   = self._N_underflow[key]
            eng_underflow_arr = self._eng_underflow[key]
            out_spec_list = [
                Spectrum(self.eng, data, in_eng, rs) for (spec, in_eng, rs) 
                    in zip(data_arr, in_eng_arr, rs_arr)
            ]
            for (spec,N,eng) in zip(
                out_spec_list, N_underflow_arr, eng_underflow_arr
            ):
                spec.underflow['N'] = N
                spec.underflow['eng'] = eng
            return out_spec_list
        else:
            raise TypeError("indexing is invalid.")

    def __setitem__(self, key, value):
        if np.issubdtype(type(key), int):
            if not np.array_equal(value.eng, self.eng):
                    raise TypeError("the energy abscissa of the new Spectrum does not agree with this Spectra.")
            self._in_eng[key] = value.in_eng
            self._rs[key] = value.rs
            if self.spec_type == 'N':
                self._grid_vals[key] = value.N
            elif self.spec_type == 'dNdE':
                self._grid_vals[key] = value.dNdE
            self._N_underflow[key] = value.underflow['N']
            self._eng_underflow[key] = value.underflow['eng']
        elif isinstance(key, slice):
            for i,spec in zip(key, value):
                if not np.array_equal(value.eng, self.eng):
                    raise TypeError("the energy abscissa of the new Spectrum does not agree with this Spectra.")
                self._in_eng[i] = spec.in_eng
                self._rs[i] = spec.rs
                if self.spec_type == 'N':
                    self._grid_vals[i] = spec.N
                elif self.spec_type == 'dNdE':
                    self._grid_vals[i] = spec.dNdE
                self._N_underflow[i] = spec.underflow['N']
                self._eng_underflow[i] = spec.underflow['eng']

    def __add__(self, other):
        """Adds two arrays of spectra together.

        Parameters
        ----------
        other : Spectra or ndarray

        Returns
        -------
        Spectra
            New `Spectra` instance which is an element-wise sum of the `Spectrum` objects in each Spectra.

        Notes
        -----
        This special function, together with `Spectra.__radd__`, allows the use of the symbol + to add arrays of spectra together. 

        See Also
        --------
        spectra.Spectra.__radd__
        """
        if np.issubclass_(type(other), Spectra):

            if not np.array_equal(self.eng, other.eng):
                raise TypeError('abscissae are different for the two spectra.')

            if self.spec_type != other.spec_type:
                raise TypeError('adding spectra of N to spectra of dN/dE.')

            out_spectra = Spectra([])
            out_spectra._spec_type = self.spec_type
            out_spectra._grid_vals = self.grid_vals + other.grid_vals
            out_spectra._eng = self.eng 
            if np.array_equal(self.in_eng, other.in_eng):
                out_spectra._in_eng = self.in_eng
            if np.array_equal(self.rs, other.rs):
                out_spectra._rs = self.rs

            return out_spectra

        elif isinstance(other, np.ndarray):

            self._grid_vals += other

        else:
            raise TypeError('adding an object that is not compatible.')

    def __radd__(self, other):
        """Adds two arrays of spectra together.

        Parameters
        ----------
        other : Spectra

        Returns
        -------
        Spectra
            New `Spectra` instance which is an element-wise sum of the `Spectrum` objects in each Spectra.

        Notes
        -----
        This special function, together with `Spectra.__add__`, allows the use of the symbol + to add two arrays of spectra together. 

        See Also
        --------
        spectra.Spectra.__add__
        """
        if npissubclass_(type(other), Spectra):

            if not np.array_equal(self.eng, other.eng):
                raise TypeError('abscissae are different from the two spectra.')

            if self.spec_type != other.spec_type:
                raise TypeError('adding spectra of N to spectra of dN/dE.')

            out_spectra = Spectra([])
            out_spectra._spec_type = self.spec_type
            out_spectra._grid_vals = (
                self.grid_vals + other.grid_vals
            )
            out_spectra._eng = self.eng 
            if np.array_equal(self.in_eng, other.in_eng):
                out_spectra._in_eng = self.in_eng
            if np.array_equal(self.rs, other.rs):
                out_spectra._rs = self.rs

            return out_spectra

        elif isinstance(other, np.ndarray):

            self._grid_vals += other

        else:
            raise TypeError('adding an object that is not compatible.')

    def __sub__(self, other):
        """Subtracts one array of spectra from another. 

        Parameters
        ----------
        other : Spectra or ndarray

        Returns
        -------
        Spectra

        Notes
        -----
        This special function, together with `Spectra.__rsub__`, allows the use of the symbol - to subtract or subtract from `Spectra` objects.

        See Also
        --------
        spectrum.Spectra.__rsub__
        """

        return self + -1*other

    def __rsub__(self, other):
        """Subtracts one array of spectra from another. 

        Parameters
        ----------
        other : Spectra or ndarray

        Returns
        -------
        Spectra

        Notes
        -----
        This special function, together with `Spectra.__rsub__`, allows the use of the symbol - to subtract or subtract from `Spectra` objects.

        See Also
        --------
        spectrum.Spectra.__sub__
        """

        return other + -1*self

    def __neg__(self):
        """Negates the spectra values. 

        Returns
        -------
        Spectra
        """

        return -1*self

    def __mul__(self, other):
        """Takes a product with this `Spectra`. 

        Parameters
        ----------
        other : Spectra, int, float, list or ndarray

        Returns
        -------
        Spectra

        Notes
        -----
        This special function, together with `Spectra.__rmul__`, allows the use of the symbol * to multiply objects with a `Spectra` object. 
        """

        if (
            np.issubdtype(type(other), float) 
            or np.issubdtype(type(other), int)
        ):
            out_spectra = Spectra([])
            out_spectra._eng = self.eng
            out_spectra._in_eng = self.in_eng
            out_spectra._rs = self.rs
            out_spectra._spec_type = self.spec_type
            out_spectra._grid_vals = self.grid_vals*other
            
            return out_spectra

        elif isinstance(other, np.ndarray):
            out_spectra = Spectra([])
            out_spectra._eng = self.eng
            out_spectra._in_eng = self.in_eng
            out_spectra._rs = self.rs
            out_spectra._spec_type = self.spec_type
            out_spectra._grid_vals = np.einsum(
                'ij,i->ij',self.grid_vals, other
            )

            return out_spectra

        elif np.issubclass_(type(other), Spectra):

            if not np.array_equal(self.eng, other.eng):
                raise TypeError('the two spectra do not have the same abscissa.')

            out_spectra = Spectra([])
            out_spectra._eng = self.eng
            if np.array_equal(self.in_eng, other.in_eng):
                out_spectra._in_eng = self.in_eng
            if np.array_equal(self.rs, other.rs):
                out_spectra._rs = self.rs
            if self.spec_type == other.spec_type:
                out_spectra._spec_type = self.spec_type
            out_spectra._grid_vals = (
                self.grid_vals * other.grid_vals
            )

            return out_spectra

    def __rmul__(self, other):
        """Takes a product with this `Spectra`. 

        Parameters
        ----------
        other : Spectra, int, float, list or ndarray

        Returns
        -------
        Spectra

        Notes
        -----
        This special function, together with `Spectra.__mul__`, allows the use of the symbol * to multiply objects with a `Spectra` object. 
        """

        if (
            np.issubdtype(type(other), float) 
            or np.issubdtype(type(other), int)
            or isinstance(other, list)
            or isinstance(other, np.ndarray)
        ):
            out_spectra = Spectra([])
            out_spectra._eng = self.eng
            out_spectra._in_eng = self.in_eng
            out_spectra._rs = self.rs
            out_spectra._spec_type = self.spec_type
            out_spectra._grid_vals = self.grid_vals*other
            
            return out_spectra

        elif np.issubclass_(type(other), Spectra):

            if not np.array_equal(self.eng, other.eng):
                raise TypeError('the two spectra do not have the same abscissa.')

            out_spectra = Spectra([])
            out_spectra._eng = self.eng
            if np.array_equal(self.in_eng, other.in_eng):
                out_spectra._in_eng = self.in_eng
            if np.array_equal(self.rs, other.rs):
                out_spectra._rs = self.rs
            if self.spec_type == other.spec_type:
                out_spectra._spec_type = self.spec_type
            out_spectra._grid_vals = (
                self.grid_vals * other.grid_vals
            )

            return out_spectra

    def __truediv__(self, other):
        """Divides Spectra by another object. 

        Parameters
        ----------
        other : ndarray, float, int, list or Spectra

        Returns
        -------
        Spectra

        Notes
        -----
        This special function, together with `Spectra.__rtruediv__`, allows the use fo the symbol / to divide `Spectra` objects. 

        See Also
        --------
        spectrum.Spectra.__rtruediv__
        """
        if np.issubclass_(type(other), Spectra):
            inv_spectra = Spectra([])
            inv_spectra._eng = other.eng
            inv_spectra._in_eng = other.in_eng
            inv_spectra._grid_vals = 1/other.grid_vals
            inv_spectra._rs = other.rs
            inv_spectra._spec_type = other.spec_type
            return self * inv_spectra
        else:
            return self * (1/other)

    def __rtruediv__(self, other):
        """Divides Spectra by another object. 

        Parameters
        ----------
        other : ndarray, float, int, list or Spectra

        Returns
        -------
        Spectra

        Notes
        -----
        This special function, together with `Spectra.__rtruediv__`, allows the use fo the symbol / to divide `Spectra` objects. 

        See Also
        --------
        spectrum.Spectra.__truediv__
        """
        inv_spectra = Spectra([])
        inv_spectra._eng = self.eng
        inv_spectra._in_eng = self.in_eng
        inv_spectra._grid_vals = 1/self.grid_vals
        inv_spectra._spec_type = self.spec_type
        inv_spectra._rs = self.rs

        return other * inv_spectra

    def switch_spec_type(self):

        log_bin_width = get_log_bin_width(self.eng)
        if self.spec_type == 'N':
            self._grid_vals = self.grid_vals/(self.eng * log_bin_width)
            self._spec_type = 'dNdE'
        elif self.spec_type == 'dNdE':
            self._grid_vals = self.grid_vals*self.eng*log_bin_width
            self._spec_type = 'N'

    def redshift(self, rs_arr):
        
        for i,(val, rs, new_rs, in_eng, N_uf, eng_uf) in enumerate(
            zip(
                self, self.rs, rs_arr, self.in_eng, 
                self.N_underflow, self.eng_underflow
            )
        ):
            spec = Spectrum(
                self.eng, val, 
                rs=rs, in_eng=in_eng, 
                spec_type=self.spec_type
            )
            spec.redshift(new_rs)
            self._grid_vals[i] = spec._data
            self.N_underflow[i] += spec.underflow['N']
            self.eng_underflow[i] += spec.underflow['eng']

        self._rs = rs_arr

    def totN(self, bound_type=None, bound_arr=None):
        """Returns the total number of particles in part of the spectra.

        The part of the `Spectrum` objects to find the total number of particles can be specified in two ways, and is specified by `bound_type`. Multiple totals can be obtained through `bound_arr`. 

        Parameters
        ----------
        bound_type : {'bin', 'eng', None}
            The type of bounds to use. Bound values do not have to be within the [0:eng.size] for `'bin'` or within the abscissa for `'eng'`. `None` should only be used when computing the total particle number in the spectrum. For `'bin'`, bounds are specified as the bin boundary, with 0 being the left most boundary, 1 the right-hand of the first bin and so on. This is equivalent to integrating over a histogram. For `'eng'`, bounds are specified by energy values.

        bound_arr : ndarray, optional
            An array of boundaries (bin or energy), between which the total number of particles will be computed. If bound_arr = None, but bound_type is specified, the total number of particles in each bin is computed. If both bound_type and bound_arr = None, then the total number of particles in the spectrum is computed.

        Returns
        -------
        ndarray
            Total number of particles in the spectrum. 

        """
        log_bin_width = get_log_bin_width(self.eng)

        # Using the broadcasting rules here. 
        if self.spec_type == 'dNdE':
            dNdlogE = np.einsum(
                'ij,j->ij',self.grid_vals,self.eng
            )
        elif self.spec_type == 'N':
            dNdlogE = np.einsum(
                'ij,j->ij', self.grid_vals, 1/log_bin_width
            )

        if bound_type is not None:

            if bound_arr is None:

                return dNdlogE * log_bin_width

            if bound_type == 'bin':

                if not all(np.diff(bound_arr) >= 0):
                    raise TypeError('bound_arr must have increasing entries.')

                # Size is number of totals requested x number of Spectrums.
                N_in_bin = np.zeros((bound_arr.size - 1, self.in_eng.size))

                if bound_arr[0] > self.eng.size or bound_arr[-1] < 0:
                    return N_in_bin

                for i, (low,upp) in enumerate(
                    (bound_arr[:-1], bound_arr[1:])
                ):
                    # Set the lower and upper bounds, including case where
                    # low and upp are outside of the bins. 
                    if low > self.eng.size or upp < 0:
                        continue

                    low_ceil  = int(np.ceil(low))
                    low_floor = int(np.floor(low))
                    upp_ceil  = int(np.ceil(upp))
                    upp_floor = int(np.floor(upp))

                    # Sum the bins that are completely between the bounds. 

                    N_full_bins = np.dot(
                        dNdlogE[:,low_ceil:upp_floor],
                        log_bin_width[low_ceil:upp_floor]
                    ) 

                    N_part_bins = np.zeros_like(self.in_eng)

                    if low_floor == upp_floor or low_ceil == upp_ceil:
                        # Bin indices are within the same bin. 
                        # The second requirement covers the case where
                        # upp_ceil is eng.size. 
                        N_part_bins += (
                            dNdlogE[:,low_floor] * (upp - low)
                            * log_bin_width[low_floor]
                        )
                    else:
                        # Add up part of the bin for the low partial bin
                        # and the high partial bin. 
                        N_part_bins += (
                            dNdlogE[:,low_floor] * (low_ceil - low)
                            * log_bin_width[low_floor]
                        )
                        if upp_floor < self.eng.size:
                            # If upp_floor is eng.size then there is
                            # no partial bin for the upper index. 
                            N_part_bins += (
                                dNdlogE[:,upp_floor] * (upp - upp_floor)
                                * log_bin_width[upp_floor]
                            )

                    N_in_bin[i] = N_full_bins + N_part_bins

                return N_in_bin

            if bound_type == 'eng':
                bin_boundary = get_bin_bound(self.eng)
                eng_bin_ind = np.interp(
                    np.log(bound_arr),
                    np.log(bin_boundary), np.arange(bin_boundary.size),
                    left = -1, right = self.eng.size + 1
                )

                return self.totN('bin', eng_bin_ind)

        else:
            return (
                np.dot(dNdlogE, log_bin_width) + np.sum(self.N_underflow)
            )

    def toteng(self, bound_type=None, bound_arr=None):
        """Returns the total energy of particles in part of the spectra.

        The part of the `Spectrum` objects to find the total energy of particles can be specified in two ways, and is specified by `bound_type`. Multiple totals can be obtained through `bound_arr`. 

        Parameters
        ----------
        bound_type : {'bin', 'eng', None}
            The type of bounds to use. Bound values do not have to be within the [0:eng.size] for `'bin'` or within the abscissa for `'eng'`. `None` should only be used when computing the total particle number in the spectrum. For `'bin'`, bounds are specified as the bin boundary, with 0 being the left most boundary, 1 the right-hand of the first bin and so on. This is equivalent to integrating over a histogram. For `'eng'`, bounds are specified by energy values.

        bound_arr : ndarray, optional
            An array of boundaries (bin or energy), between which the total number of particles will be computed. If bound_arr = None, but bound_type is specified, the total number of particles in each bin is computed. If both bound_type and bound_arr = None, then the total number of particles in the spectrum is computed.

        Returns
        -------
        ndarray
            Total energy of particles in the spectrum. 

        """
        log_bin_width = get_log_bin_width(self.eng)

        # Using the broadcasting rules here. 
        if self.spec_type == 'dNdE':
            dNdlogE = self.grid_vals * self.eng
        elif self.spec_type == 'N':
            dNdlogE = self.grid_vals / log_bin_width

        if bound_type is not None:

            if bound_arr is None:

                return dNdlogE * self.eng * log_bin_width

            if bound_type == 'bin':

                if not all(np.diff(bound_arr) >= 0):
                    raise TypeError('bound_arr must have increasing entries.')

                # Size is number of totals requested x number of Spectrums. 
                eng_in_bin = np.zeros((bound_arr.size - 1, self.in_eng.size))

                if bound_arr[0] > self.eng.size or bound_arr[-1] < 0:
                    return eng_in_bin

                for i, (low,upp) in enumerate(
                    (bound_arr[:-1], bound_arr[1:])
                ):

                    # Set the lower and upper bounds, including case where
                    # low and upp are outside of the bins. 
                    if low > self.eng.size or upp < 0:
                        continue

                    low_ceil  = int(np.ceil(low))
                    low_floor = int(np.floor(low))
                    upp_ceil  = int(np.ceil(upp))
                    upp_floor = int(np.floor(upp))

                    # Sum the bins that are completely between the bounds.

                    eng_full_bins = np.dot(
                        dNdlogE[:,low_ceil:upp_floor]
                        * self.eng[low_ceil:upp_floor],
                        log_bin_width[low_ceil:upp_floor]
                    )

                    eng_part_bins = np.zeros_like(self.in_eng)

                    if low_floor == upp_floor or low_ceil == upp_ceil:

                        # Bin indices are within the same bin. The second
                        # requirement covers the case where upp_ceil is
                        # eng.size. 

                        eng_part_bins += (
                            dNdlogE[:,low_floor] * (upp - low)
                            * self.eng[low_floor] * log_bin_width[low_floor]
                        )

                    else:
                        # Add up part of the bin for the low partial bin
                        # and the high partial bin. 
                        eng_part_bins += (
                            dNdlogE[:,low_floor] * (low_ceil - low)
                            * self.eng[low_floor] * log_bin_width[low_floor]
                        )

                        if upp_floor < eng.size:
                            # If upp_floor is eng.size, then there is no
                            # partial bin for the upper index. 
                            eng_part_bins += (
                                dNdlogE[:,upp_floor] * (upp - upp_floor)
                                * self.eng[upp_floor] 
                                * log_bin_width[upp_floor]
                            )

                    eng_in_bin[i] = eng_full_bins + eng_part_bins

                return eng_in_bin

            if bound_type == 'eng':
                bin_boundary = get_bin_bound(self.eng)
                eng_bin_ind = np.interp(
                    np.log(bound_arr),
                    np.log(bin_boundary), np.arange(bin_boundary.size),
                    left = -1, right = self.eng.size + 1
                )

                return self.toteng('bin', eng_bin_ind)

        else:
            return (
                np.dot(dNdlogE, self.eng*log_bin_width)
                + np.sum(self.eng_underflow)
            )

    def integrate_each_spec(self, weight=None):
        """Sums over each individual spectrum with some weight. 

        The weight is over each energy bin, and has the same length as `self.eng`.   

        Parameters
        ----------
        weight : ndarray, optional
            The weight in each energy bin, with weight of 1 for every bin if not specified. 

        Returns
        -------
        ndarray
            An array of weighted sums, one for each spectrum in this `Spectra`.
        """
        if weight is None:
            weight = np.ones_like(self.eng)

        if isinstance(weight, np.ndarray):
            if weight.ndim == 1:
                return np.dot(self.grid_vals, weight)
            elif weight.ndim == 2:
                return np.sum(self.grid_vals*weight, axis=1)
            else:
                raise TypeError('weight does not have the correct dimensions.')
        else:
            raise TypeError('weight must be an ndarray of the correct dimensions.')

    def sum_specs(self, weight=None):
        """Sums all of spectra with some weight. 

        The weight is over each spectrum, and has the same length as `self.in_eng` and `self.rs`. 

        Parameters
        ----------
        weight : ndarray or Spectrum, optional
            The weight in each redshift bin, with weight of 1 for every bin if not specified.

        Returns
        -------
        Spectrum
            A `Spectrum` of the weighted sum of the spectra.  

        """
        if weight is None:
            weight = np.ones_like(self.rs)

        if isinstance(weight, np.ndarray):
            new_data = np.dot(weight, self.grid_vals)
            return Spectrum(self.eng, new_data, spec_type=self.spec_type)
        elif isinstance(weight, Spectrum):
            new_data = np.dot(weight._data, self.grid_vals)
            return Spectrum(
                self.eng, new_data, spec_type=weight.spec_type
            )
        else:
            raise TypeError('weight must be an ndarray or spectrum.')

    def rebin(self, out_eng):
        """ Re-bins all `Spectrum` objects according to a new abscissa.

        Rebinning conserves total number and total energy.
        
        Parameters
        ----------
        out_eng : ndarray
            The new abscissa to bin into. If `self.eng` has values that are smaller than `out_eng[0]`, then the new underflow will be filled. If `self.eng` has values that exceed `out_eng[-1]`, then an error is returned.

        rebin_type : {'1D', '2D'}, optional
            Whether to rebin each `Spectrum` separately (`'1D'`), or the whole `Spectra` object at once (`'2D'`). Default is `'2D'`.

        See Also
        --------
        spec.spectools.rebin_N_2D_arr
        """

        if not np.all(np.diff(out_eng) > 0):
            raise TypeError('new abscissa must be ordered in increasing energy.')

        # Get the bin indices that the current abscissa (self.eng)
        # corresponds to in the new abscissa (new_eng). Bin indices are 
        # with respect to bin centers. 

        # Add an additional bin at the lower end of out_eng so that
        # underflow can be treated easily. 

        first_bin_eng = np.exp(
            np.log(out_eng[0]) 
            - (np.log(out_eng[1]) - np.log(out_eng[0]))
        )
        new_eng = np.insert(out_eng, 0, first_bin_eng)

        # Find the relative bin indices for self.eng. The first bin in 
        # new_eng has bin index -1. Underflow has index -2, overflow
        # corresponds to new_eng.size

        bin_ind = np.interp(
            self.eng, new_eng, np.arange(new_eng.size)-1, 
            left = -2, right = new_eng.size
        )

        # Locate where bin_ind is below 0, above self.length-1 
        # or in between. 

        ind_low  = np.where(bin_ind < 0)[0]
        ind_high = np.where(bin_ind == new_eng.size)[0]
        ind_reg  = np.where(
            (bin_ind >= 0) & (bin_ind <= new_eng.size - 1)
        )[0]

        if ind_high.size > 0: 
            warnings.warn("The new abscissa lies below the old one: only bins that lie within the new abscissa will be rebinned, bins above the abscissa will be discarded.", RuntimeWarning)

        # These arrays are of size in_eng x eng. 
        N_arr = self.totN('bin')
        toteng_arr = self.toteng('bin')

        N_arr_low  = N_arr[:,ind_low]
        N_arr_high = N_arr[:,ind_high]
        N_arr_reg  = N_arr[:,ind_reg]

        toteng_arr_low = toteng_arr[:,ind_low]

        # Factor depends on the spec_type. 
        if self.spec_type == 'dNdE':
            # E dlog E of the new array. 
            fac = new_eng * get_log_bin_width(new_eng)
        elif self.spec_type == 'N':
            fac = np.ones_like(new_eng)


        # Regular bins first. 

        # reg_bin_low is the array of the lower bins to be allocated the
        # particles in N_arr_reg, similarly reg_bin_upp. This should also
        # take care of the case where bin_ind is an integer. 

        reg_bin_low = np.floor(bin_ind[ind_reg]).astype(int)
        reg_bin_upp = reg_bin_low + 1

        # Takes care of the case where eng[-1] = new_eng[-1], which falls
        # under regular indices. Remember the extra bin on the left. 
        reg_bin_low[reg_bin_low == new_eng.size-2] = new_eng.size - 3
        reg_bin_upp[reg_bin_upp == new_eng.size-1] = new_eng.size - 2

        # Split the particles up into the lower bin and upper bin. 
        # Remember there's an extra bin on the left when indexing into
        # new_E_dlogE. 
        reg_data_low = (
            (reg_bin_upp - bin_ind[ind_reg]) * N_arr_reg
            / fac[reg_bin_low+1]
        )
        reg_data_upp = (
            (bin_ind[ind_reg] - reg_bin_low) * N_arr_reg
            / fac[reg_bin_upp+1]
        )

        # Handle low bins. 
        low_bin_low = np.floor(bin_ind[ind_low]).astype(int)

        N_above_underflow = np.sum(
            (bin_ind[ind_low] - low_bin_low) * N_arr_low, axis = 1
        )
        eng_above_underflow = N_above_underflow * new_eng[1]

        N_underflow = np.sum(N_arr_low, axis=1) - N_above_underflow
        eng_underflow = (
            np.sum(toteng_arr_low, axis=1) - eng_above_underflow
        )
        low_data = N_above_underflow/fac[1]

        # Add up, obtain the new dN/dE. 

        new_data = np.zeros((self.in_eng.size, new_eng.size))
        new_data[:,1] += low_data

        np.add.at(new_data, (slice(None), reg_bin_low+1), reg_data_low)
        np.add.at(new_data, (slice(None), reg_bin_upp+1), reg_data_upp)

        # new_data[:,reg_bin_low+1] += reg_data_low
        # new_data[:,reg_bin_upp+1] += reg_data_upp

        self._eng = new_eng[1:]
        self._grid_vals = new_data[:,1:]
        self._N_underflow += N_underflow
        self._eng_underflow += eng_underflow

    def append(self, spec):
        """Appends a new Spectrum. 

        Parameters
        ----------
        spec : Spectrum
            The new spectrum to append.
        """
        # Checks if spec_arr is empty
        if self.eng.size != 0:
            if not np.array_equal(self.eng, spec.eng):
                raise TypeError("new Spectrum does not have the same energy abscissa.")

        if self.spec_type != spec.spec_type:
            raise TypeError("new Spectrum is not of the same type as the Spectra.")

        self._in_eng = np.append(self.in_eng, spec.in_eng)
        self._rs = np.append(self.rs, spec.rs)
        self._N_underflow = np.append(self._N_underflow, spec.underflow['N'])
        self._eng_underflow = np.append(
            self._eng_underflow, spec.underflow['eng']
        )
        
        if self.eng.size == 0:
            self._eng = spec.eng
            self._grid_vals = np.atleast_2d(spec._data)
        else:
            self._grid_vals = np.concatenate(
                (self.grid_vals, np.atleast_2d(spec._data))
            )

    def at_rs(
        self, new_rs, interp_type='val', 
        bounds_err=None, fill_value=np.nan
    ):
        """Interpolates the transfer function at a new redshift. 

        Interpolation is logarithmic. 

        Parameters
        ----------
        new_rs : ndarray
            The redshifts or redshift bin indices at which to interpolate. 
        interp_type : {'val', 'bin'}
            The type of interpolation. 'bin' uses bin index, while 'val' uses the actual redshift. 
        bounds_err : bool, optional
            Whether to return an error if outside of the bounds for the interpolation. 
        """
        if (
            not np.all(np.diff(self.rs)) > 0
            and not np.all(np.diff(self.rs)) < 0
        ):
            raise TypeError('redshift abscissa must be strictly increasing or decreasing for interpolation.')

        interp_func = interpolate.interp1d(
            np.log(self.rs), self.grid_vals, axis=0,
            bounds_error=bounds_err, fill_value=fill_value
        )

        if interp_type == 'val':

            new_spectra = Spectra([])
            new_spectra._eng = self.eng
            new_spectra._in_eng = -np.ones_like(new_rs)
            new_spectra._rs = new_rs
            new_spectra._grid_vals = interp_func(np.log(new_rs))
            new_spectra._spec_type = self.spec_type

            return new_spectra

        elif interp_type == 'bin':

            log_new_rs = np.interp(
                np.log(new_rs), np.arange(self.rs.size), np.log(self.rs)
            )

            return self.at_rs(np.exp(log_new_rs))

        else:
            raise TypeError('invalid interp_type specified.')

    def plot(self, ax, ind=None, step=1, indtype='ind', 
    fac=1, **kwargs):
        """Plots the contained `Spectrum` objects. 

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            The axis handle of the figure to show the plot in.
        ind : int, float, tuple or ndarray, optional.
            Index or redshift of Spectrum to plot, or a tuple of indices or redshifts providing a range of Spectrum to plot, or a list of indices or redshifts of Spectrum to plot.
        step : int, optional
            The number of steps to take before choosing one Spectrum to plot.
        indtype : {'ind', 'rs'}, optional
            Specifies whether ind is an index or an abscissa value.
        abs_plot :  bool, optional
            Plots the absolute value if true.
        fac : ndarray, optional
            Factor to multiply the array by. 
        **kwargs : optional
            All additional keyword arguments to pass to matplotlib.plt.plot. 

        Returns
        -------
        matplotlib.figure
        """

        if ind is None:
            return self.plot(
                ax, ind=np.arange(self.rs.size), fac=fac, **kwargs
            )

        if indtype == 'ind':

            if np.issubdtype(type(ind), np.int64):
                return ax.plot(
                    self.eng, self.grid_vals[ind]*fac, **kwargs
                )

            elif isinstance(ind, tuple):
                spec_to_plot = np.stack(
                    [
                        self.grid_vals[i]*fac 
                        for i in np.arange(ind[0], ind[1], step)
                    ], axis = -1
                )
                return ax.plot(self.eng, spec_to_plot, **kwargs)

            elif isinstance(ind, np.ndarray) or isinstance(ind, list):
                spec_to_plot = np.stack(
                    [self.grid_vals[i]*fac for i in ind], axis=-1
                )
                return ax.plot(self.eng, spec_to_plot, **kwargs)

            else:
                raise TypeError('invalid ind.')

        elif indtype == 'rs':

            if (
                np.issubdtype(type(ind), np.int64)
                or np.issubdtype(type(ind), np.float64)
            ):
                return self.at_rs(np.array([ind])).plot(
                    ax, ind=0, fac=fac, **kwargs
                )

            elif isinstance(ind, tuple):
                rs_to_plot = np.arange(ind[0], ind[1], step)
                return self.at_rs(rs_to_plot).plot(
                    ax, fac=fac, **kwargs
                )

            elif isinstance(ind, np.ndarray) or isinstance(ind, list):
                return self.at_rs(ind).plot(
                    ax, fac=fac, **kwargs
                )

        else: 
            raise TypeError('indtype must be either ind or rs.')

