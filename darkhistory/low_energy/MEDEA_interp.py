import numpy as np
import scipy.interpolate as interp
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def make_interpolators():
    """Creates cubic splines that interpolate the Medea Data

    Parameters
    ----------
    xe : float
        The ionization fraction ne/nH.

    Returns
    -------
    RegularGridInterpolator : interp_heat, interp_lyman, interp_ionH, interp_ionHe, interp_lowE_photon
        interpolating function for energy deposited in heat, H excitation, H ionization, He (double?) ionization, and production of low energy photons.
        The syntax is a bit tricky.  For example, to figure out the energy deposited in heat at (E, x_HII) = (20eV,.12) and (22eV,.5), one must use
        interp_heat([[20,.12],[22,.5]])
    """

    # 6 energy values: 14, 30, 60, 100, 300, 3000eV
    # 26 x_HII values: ranging from 0 to 1 (non-linearly spaced)
    engs = [14, 30, 60, 100, 300, 3000]
    xHII = []
    heat, lyman, ionH, ionHe, lowE_photon = [ [ [] for i in range(len(engs))]
                                             for j in range(5)]

    for i, num in enumerate(engs, start=0):
        with open('results-'+str(num)+'ev-xH-xHe_e-10-yp024.dat','r') as f:
            lines_list = f.readlines()
            if i==0:
                xHII = [np.log(float(line.split('\t')[0])) for line in lines_list[2:]]
            heat[i], lyman[i], ionH[i], ionHe[i], lowE_photon[i] = [[np.log(float(line.split('\t')[k])) for line in lines_list[2:]] for k in [1,2,3,4,5]]

    heat, lyman, ionH, ionHe, lowE_photon = np.array(heat), np.array(lyman), np.array(ionH), np.array(ionHe), np.array(lowE_photon)

    engs = np.log(engs)
    interp_heat = interp.RegularGridInterpolator((engs,xHII),heat)
    interp_lyman = interp.RegularGridInterpolator((engs,xHII),lyman)
    interp_ionH = interp.RegularGridInterpolator((engs,xHII),ionH)
    interp_ionHe = interp.RegularGridInterpolator((engs,xHII),ionHe)
    interp_lowE_photon = interp.RegularGridInterpolator((engs,xHII),lowE_photon)

    x = np.linspace(engs[0],engs[-1],100)
    y = np.linspace(xHII[0],xHII[-1],100)
    points = np.array( [[[a,b] for a in x] for b in y ])
    x, y = np.meshgrid(x,y)
    #points = np.array([x,y]).T
    z = interp_ionH(points)
    print(x.shape)
    print(y.shape)
    print(z.shape)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(x,y,z)

    engs, xHII = np.meshgrid(engs,xHII)
    engs = engs.flatten()
    xHII = xHII.flatten()
    ionH = ionH.T.flatten()
    ax.scatter(engs, xHII, ionH, c='red', marker='.', lw=0)

    ax.set_xlabel("ln(E) (eV)")
    ax.set_ylabel("ln(x_HII)")
    ax.set_zlabel("ln(Deposition) (%)")
    plt.show()

"""
    print(len(engs),len(xHII),len(heat))
    print(np.exp(engs),"\n")
    print(np.exp(xHII),"\n")
    print(np.exp(heat),"\n")
    return interp_heat, interp_lyman, interp_ionH, interp_ionHe, interp_lowE_photon
    print("xHII: ", xHII,"\n")
    print("heat: ", heat[5],"\n")
    print("lyman: ", lyman[5], "\n")
    print("ionH: ", ionH[5], "\n")
    print("ionHe: ", ionHe[5], "\n")
    print("lowE_photon: ", lowE_photon[5], "\n")
"""

def use_interps():
    interp_heat, interp_lyman, interp_ionH, interp_He, interp_lowE_photon = make_interpolators()
    points = np.array([[60,.00015],[60,.000175],[45,.00015]])
    print(interp_heat(points))
