# Copyright 2021 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This module implements the quantum states upon which a quantum circuits acts on.
"""

from __future__ import annotations

from typing import Sequence

from mrmustard import math, settings
from mrmustard.math.parameter_set import ParameterSet
from mrmustard.math.parameters import update_symplectic
from mrmustard.physics import fock, gaussian
from mrmustard.utils.typing import RealMatrix, Scalar, Vector

from .abstract import State
from .utils import make_parameter

__all__ = [
    "Vacuum",
    "SqueezedVacuum",
    "Coherent",
    "Thermal",
    "DisplacedSqueezed",
    "TMSV",
    "Gaussian",
    "Fock",
]


class Vacuum(State):
    r"""The N-mode vacuum state."""

    def __init__(self, num_modes: int):
        cov = gaussian.vacuum_cov(num_modes)
        means = gaussian.vacuum_means(num_modes)
        super().__init__(cov=cov, means=means)


class Coherent(State):
    r"""The N-mode coherent state.

    Equivalent to applying a displacement to the vacuum state:

    .. code-block::

        Coherent(x=0.5, y=0.2) == Vacuum(1) >> Dgate(x=0.5, y=0.2)    # True

    Parallelizable over x and y:

    .. code-block::

        Coherent(x=[1.0, 2.0], y=[-1.0, -2.0]) == Coherent(x=1.0, y=-1.0) & Coherent(x=2.0, y=-2.0)  # True

    Can be used to model a heterodyne detection:

    .. code-block::

        Gaussian(2) << Coherent(x=1.0, y=0.0)[1]  # e.g. heterodyne on mode 1, leftover state on mode 0

    Note that the values of x and y are automatically rescaled by 1/(2*sqrt(mrmustard.settings.HBAR)).

    Args:
        x (float or List[float]): The x-displacement of the coherent state.
        y (float or List[float]): The y-displacement of the coherent state.
        x_trainable (bool): Whether the x-displacement is trainable.
        y_trainable (bool): Whether the y-displacement is trainable.
        x_bounds (float or None, float or None): The bounds of the x-displacement.
        y_bounds (float or None, float or None): The bounds of the y-displacement.
        modes (optional List[int]): The modes of the coherent state.
        cutoffs (Sequence[int], default=None): set to force the cutoff dimensions of the state
        normalize (bool, default False): whether to normalize the leftover state when projecting onto ``Coherent``
    """

    def __init__(
        self,
        x: float | list[float] | None = 0.0,
        y: float | list[float] | None = 0.0,
        x_trainable: bool = False,
        y_trainable: bool = False,
        x_bounds: tuple[float | None, float | None] = (None, None),
        y_bounds: tuple[float | None, float | None] = (None, None),
        modes: Sequence[int] | None = None,
        cutoffs: Sequence[int] | None = None,
        normalize: bool = False,
    ):
        self._normalize = normalize

        self._parameter_set = ParameterSet()
        self._add_parameter(make_parameter(x_trainable, x, "x", x_bounds))
        self._add_parameter(make_parameter(y_trainable, y, "y", y_bounds))

        means = gaussian.displacement(x, y)
        cov = gaussian.vacuum_cov(means.shape[-1] // 2)
        super().__init__(cov=cov, means=means, cutoffs=cutoffs, modes=modes)

    @property
    def means(self):
        return gaussian.displacement(self.x.value, self.y.value)


class SqueezedVacuum(State):
    r"""The N-mode squeezed vacuum state.

    Equivalent to applying a squeezing gate to the vacuum state:

    .. code::

      >>> SqueezedVacuum(r=0.5, phi=0.2) == Vacuum(1) >> Sgate(r=0.5, phi=0.2)
      True

    Parallelizable over r and phi:
    .. code::

      >>> SqueezedVacuum(r=[1.0, 2.0], phi=[-1.0, -2.0]) == SqueezedVacuum(r=1.0, phi=-1.0) & SqueezedVacuum(r=2.0, phi=-2.0)
      True

    Can be used to model a heterodyne detection with result 0.0:
    .. code::

      >>> Gaussian(2) << SqueezedVacuum(r=10.0, phi=0.0)[1]  # e.g. homodyne on x quadrature on mode 1 with result 0.0
      # leftover state on mode 0

    Args:
        r (float): the squeezing magnitude
        phi (float): The squeezing phase.
        r_trainable (bool): Whether the squeezing magnitude is trainable.
        phi_trainable (bool): Whether the squeezing phase is trainable.
        r_bounds (tuple): The bounds of the squeezing magnitude.
        phi_bounds (tuple): The bounds of the squeezing phase.
        modes (list): The modes of the squeezed vacuum state.
        cutoffs (Sequence[int], default=None): set to force the cutoff dimensions of the state
        normalize (bool, default False): whether to normalize the leftover state when projecting onto ``SqueezedVacuum``,
    """

    def __init__(
        self,
        r: Scalar | Vector = 0.0,
        phi: Scalar | Vector = 0.0,
        r_trainable: bool = False,
        phi_trainable: bool = False,
        r_bounds: tuple[float | None, float | None] = (0, None),
        phi_bounds: tuple[float | None, float | None] = (None, None),
        modes: Sequence[int] | None = None,
        cutoffs: Sequence[int] | None = None,
        normalize: bool = False,
    ):
        self._modes = modes
        self._normalize = normalize

        self._parameter_set = ParameterSet()
        self._add_parameter(make_parameter(r_trainable, r, "r", r_bounds))
        self._add_parameter(make_parameter(phi_trainable, phi, "phi", phi_bounds))

        cov = gaussian.squeezed_vacuum_cov(r, phi)
        means = gaussian.vacuum_means(
            cov.shape[-1] // 2,
        )
        super().__init__(cov=cov, means=means, cutoffs=cutoffs)

    @property
    def cov(self):
        return gaussian.squeezed_vacuum_cov(self.r.value, self.phi.value)


class TMSV(State):
    r"""The 2-mode squeezed vacuum state.

    Equivalent to applying a 50/50 beam splitter to a pair of squeezed vacuum states:

    .. code::

      >>> TMSV(r=0.5, phi=0.0) == Vacuum(2) >> Sgate(r=[0.5,0.5], phi=[0.0, np.pi]) >> BSgate(theta=-np.pi/4)
      True

    Args:
        r (float): The squeezing magnitude.
        phi (float): The squeezing phase.
        r_trainable (bool): Whether the squeezing magnitude is trainable.
        phi_trainable (bool): Whether the squeezing phase is trainable.
        r_bounds (tuple): The bounds of the squeezing magnitude.
        phi_bounds (tuple): The bounds of the squeezing phase.
        modes (list): The modes of the two-mode squeezed vacuum state. Must be of length 2.
        cutoffs (Sequence[int], default=None): set to force the cutoff dimensions of the state
        normalize (bool, default False): whether to normalize the leftover state when projecting onto ``TMSV``
    """

    def __init__(
        self,
        r: Scalar | Vector = 0.0,
        phi: Scalar | Vector = 0.0,
        r_trainable: bool = False,
        phi_trainable: bool = False,
        r_bounds: tuple[float | None, float | None] = (0, None),
        phi_bounds: tuple[float | None, float | None] = (None, None),
        modes: Sequence[int] | None = (0, 1),
        cutoffs: Sequence[int] | None = None,
        normalize: bool = False,
    ):
        self._normalize = normalize

        self._parameter_set = ParameterSet()
        self._add_parameter(make_parameter(r_trainable, r, "r", r_bounds))
        self._add_parameter(make_parameter(phi_trainable, phi, "phi", phi_bounds))

        cov = gaussian.two_mode_squeezed_vacuum_cov(r, phi)
        means = gaussian.vacuum_means(2)
        super().__init__(cov=cov, means=means, cutoffs=cutoffs)

    @property
    def cov(self):
        return gaussian.two_mode_squeezed_vacuum_cov(self.r.value, self.phi.value)


class Thermal(State):
    r"""The N-mode thermal state.

    Equivalent to applying additive noise to the vacuum:

    .. code::

        >>> Thermal(nbar=0.31) == Vacuum(1) >> AdditiveNoise(0.62)  # i.e. 2*nbar + 1 (from vac) in total
        True

    Parallelizable over ``nbar``:

    .. code::

        >>> Thermal(nbar=[0.1, 0.2]) == Thermal(nbar=0.1) & Thermal(nbar=0.2)
        True

    Args:
        nbar (float or List[float]): the expected number of photons in each mode
        nbar_trainable (bool): whether the ``nbar`` is trainable
        nbar_bounds (tuple): the bounds of the ``nbar``
        modes (list): the modes of the thermal state
        cutoffs (Sequence[int], default=None): set to force the cutoff dimensions of the state
        normalize (bool, default False): whether to normalize the leftover state when projecting onto ``Thermal``
    """

    def __init__(
        self,
        nbar: Scalar | Vector = 0.0,
        nbar_trainable: bool = False,
        nbar_bounds: tuple[float | None, float | None] = (0, None),
        modes: Sequence[int] | None = None,
        cutoffs: Sequence[int] | None = None,
        normalize: bool = False,
    ):
        self._modes = modes
        self._normalize = normalize

        self._parameter_set = ParameterSet()
        self._add_parameter(make_parameter(nbar_trainable, nbar, "nbar", nbar_bounds))

        cov = gaussian.thermal_cov(self.nbar.value)
        means = gaussian.vacuum_means(cov.shape[-1] // 2)
        super().__init__(cov=cov, means=means, cutoffs=cutoffs)

    @property
    def cov(self):
        return gaussian.thermal_cov(self.nbar.value)


class DisplacedSqueezed(State):
    r"""The N-mode displaced squeezed state.

    Equivalent to applying a displacement to the squeezed vacuum state:

    .. code::

        >>> DisplacedSqueezed(r=0.5, phi=0.2, x=0.3, y=-0.7) == SqueezedVacuum(r=0.5, phi=0.2) >> Dgate(x=0.3, y=-0.7)
        True

    Parallelizable over ``r``, ``phi``, ``x``, ``y``:

    .. code::

        >>> DisplacedSqueezed(r=[0.1, 0.2], phi=[0.3, 0.4], x=[0.5, 0.6], y=[0.7, 0.8]) == DisplacedSqueezed(r=0.1, phi=0.3, x=0.5, y=0.7) & DisplacedSqueezed(r=0.2, phi=0.4, x=0.6, y=0.8)
        True

    Can be used to model homodyne detection:

    .. code::

      >>> Gaussian(2) << DisplacedSqueezed(r=10, phi=np.pi, y=0.3)[1]  # e.g. homodyne on mode 1, p quadrature, result 0.3
      # leftover state on mode 0

    Args:
        r (float or List[float]): the squeezing magnitude
        phi (float or List[float]): the squeezing phase
        x (float or List[float]): the displacement in the x direction
        y (float or List[float]): the displacement in the y direction
        r_trainable (bool): whether the squeezing magnitude is trainable
        phi_trainable (bool): whether the squeezing phase is trainable
        x_trainable (bool): whether the displacement in the x direction is trainable
        y_trainable (bool): whether the displacement in the y direction is trainable
        r_bounds (tuple): the bounds of the squeezing magnitude
        phi_bounds (tuple): the bounds of the squeezing phase
        x_bounds (tuple): the bounds of the displacement in the x direction
        y_bounds (tuple): the bounds of the displacement in the y direction
        modes (list): the modes of the displaced squeezed state.
        cutoffs (Sequence[int], default=None): set to force the cutoff dimensions of the state
        normalize (bool, default False): whether to normalize the leftover state when projecting onto ``DisplacedSqueezed``
    """

    def __init__(
        self,
        r: Scalar | Vector = 0.0,
        phi: Scalar | Vector = 0.0,
        x: Scalar | Vector = 0.0,
        y: Scalar | Vector = 0.0,
        r_trainable: bool = False,
        phi_trainable: bool = False,
        x_trainable: bool = False,
        y_trainable: bool = False,
        r_bounds: tuple[float | None, float | None] = (0, None),
        phi_bounds: tuple[float | None, float | None] = (None, None),
        x_bounds: tuple[float | None, float | None] = (None, None),
        y_bounds: tuple[float | None, float | None] = (None, None),
        modes: Sequence[int] | None = None,
        cutoffs: Sequence[int] | None = None,
        normalize: bool = False,
    ):
        self._modes = modes
        self._normalize = normalize

        self._parameter_set = ParameterSet()
        self._add_parameter(make_parameter(x_trainable, x, "x", x_bounds))
        self._add_parameter(make_parameter(y_trainable, y, "y", y_bounds))
        self._add_parameter(make_parameter(r_trainable, r, "r", r_bounds))
        self._add_parameter(make_parameter(phi_trainable, phi, "phi", phi_bounds))

        cov = gaussian.squeezed_vacuum_cov(r, phi)
        means = gaussian.displacement(x, y)
        super().__init__(cov=cov, means=means, cutoffs=cutoffs, modes=modes)

    @property
    def cov(self):
        return gaussian.squeezed_vacuum_cov(self.r.value, self.phi.value)

    @property
    def means(self):
        return gaussian.displacement(self.x.value, self.y.value)


class Gaussian(State):
    r"""The N-mode Gaussian state parametrized by a symplectic matrix and N symplectic eigenvalues.

    The (mixed) Gaussian state is equivalent to applying a Gaussian symplectic transformation to a Thermal state:

    .. code::

        >>> G = Gaussian(num_modes=1, eigenvalues = np.random.uniform(settings.HBAR/2, 10.0))
        >>> G == Thermal(nbar=(G.eigenvalues*2/settings.HBAR  - 1)/2) >> Ggate(1, symplectic=G.symplectic)
        True

    Note that the 1st moments are zero unless a Dgate is applied to the Gaussian state:

    .. code::

        >>> np.allclose(Gaussian(num_modes=1).means, 0.0)
        True

    Args:
        num_modes (int): the number of modes
        eigenvalues (float or List[float]): the symplectic eigenvalues of the Gaussian state
        symplectic (np.ndarray or List[np.ndarray]): the symplectic matrix of the Gaussian state
        eigenvalues_trainable (bool): whether the eigenvalues are trainable
        symplectic_trainable (bool): whether the symplectic matrix is trainable
        eigenvalues_bounds (tuple): the bounds of the eigenvalues
        modes (optional, List[int]): the modes of the Gaussian state.
        cutoffs (Sequence[int], default=None): set to force the cutoff dimensions of the state
        normalize (bool, default False): whether to normalize the leftover state when projecting onto Gaussian
    """

    def __init__(
        self,
        num_modes: int,
        symplectic: RealMatrix = None,
        eigenvalues: Vector = None,
        symplectic_trainable: bool = False,
        eigenvalues_trainable: bool = False,
        eigenvalues_bounds: tuple[float | None, float | None] = (None, None),
        modes: list[int] = None,
        cutoffs: Sequence[int] | None = None,
        normalize: bool = False,
    ):
        if symplectic is None:
            symplectic = math.random_symplectic(num_modes=num_modes)
        if eigenvalues is None:
            eigenvalues = gaussian.math.ones(num_modes) * settings.HBAR / 2
        if math.any(math.atleast_1d(eigenvalues) < settings.HBAR / 2):
            raise ValueError(
                f"Eigenvalues cannot be smaller than hbar/2 = {settings.HBAR}/2 = {settings.HBAR/2}"
            )
        self._modes = modes
        self._normalize = normalize

        self._parameter_set = ParameterSet()
        eb = (settings.HBAR / 2, None) if eigenvalues_bounds == (None, None) else eigenvalues_bounds
        self._add_parameter(make_parameter(eigenvalues_trainable, eigenvalues, "eigenvalues", eb))
        self._add_parameter(
            make_parameter(
                symplectic_trainable,
                symplectic,
                "symplectic",
                (None, None),
                update_symplectic,
            )
        )

        cov = gaussian.gaussian_cov(symplectic, eigenvalues)
        means = gaussian.vacuum_means(cov.shape[-1] // 2)
        super().__init__(cov=cov, means=means, cutoffs=cutoffs)

    @property
    def cov(self):
        return gaussian.gaussian_cov(self.symplectic.value, self.eigenvalues.value)

    @property
    def is_mixed(self):
        return any(self.eigenvalues.value > settings.HBAR / 2)


class Fock(State):
    r"""The N-mode Fock state.

    Args:
        n (int or List[int]): the number of photons in each mode
        modes (optional, List[int]): the modes of the Fock state
        cutoffs (Sequence[int], default=None): set to force the cutoff dimensions of the state
        normalize (bool, default False): whether to normalize the leftover state when projecting onto ``Fock``
    """

    def __init__(
        self,
        n: Sequence[int],
        modes: Sequence[int] | None = None,
        cutoffs: Sequence[int] | None = None,
        normalize: bool = False,
    ):
        super().__init__(ket=fock.fock_state(n), cutoffs=cutoffs)

        self._n = [n] if isinstance(n, int) else n
        self._modes = modes
        self._normalize = normalize

    def _preferred_projection(self, other: State, mode_indices: Sequence[int]):
        r"""Preferred method to perform a projection onto this state (rather than the default one).

        E.g. ``ket << Fock([1], modes=[3])`` is equivalent to ``ket[:,:,:,1]`` if ``ket`` has 4 modes
        E.g. ``dm << Fock([1], modes=[1])`` is equivalent to ``dm[:,1,:,1]`` if ``dm`` has 2 modes

        Args:
            other: the state to project onto this state
            mode_indices: the indices of the modes of other that we want to project onto self
        """
        getitem = []
        cutoffs = []
        used = 0
        for i, _ in enumerate(other.modes):
            if i in mode_indices:
                getitem.append(self._n[used])
                cutoffs.append(self._n[used] + 1)
                used += 1
            else:
                getitem.append(slice(None))
                cutoffs.append(other.cutoffs[i])
        output = (
            other.ket(cutoffs)[tuple(getitem)]
            if other.is_hilbert_vector
            else other.dm(cutoffs)[tuple(getitem) * 2]
        )
        if self._normalize:
            return fock.normalize(output, is_dm=other.is_mixed)
        return output
