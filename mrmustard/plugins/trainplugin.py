import numpy as np
from scipy.linalg import expm
from mrmustard._typing import *
from mrmustard.backends import BackendInterface


class TrainPlugin:

    _backend: BackendInterface

    def __init__(self):
        self.euclidean_opt = self.__class__._backend.DefaultEuclideanOptimizer()

    def new_variable(self, value, bounds: Tuple[Optional[float], Optional[float]], name: str) -> Trainable:
        r"""
        Returns a new trainable variable from the current backend
        with initial value set by `value` and bounds set by `bounds`.
        Arguments:
            value (float): The initial value of the variable
            bounds (Tuple[float, float]): The bounds of the variable
            name (str): The name of the variable
        Returns:
            variable (Trainable): The new variable
        """
        return self._backend.new_variable(value, bounds, name)

    def new_constant(self, value, name: str) -> Tensor:
        r"""
        Returns a new constant (non-trainable) tensor from the current backend
        with initial value set by `value`.
        Arguments:
            value (numeric): The initial value of the tensor
            name (str): The name of the constant
        Returns:
            tensor (Tensor): The new constant tensor
        """
        return self._backend.new_constant(value, name)

    def new_symplectic(self, num_modes: int) -> Tensor:
        r"""
        Returns a new symplectic matrix from the current backend
        with `num_modes` modes.
        Arguments:
            num_modes (int): The number of modes in the symplectic matrix
        Returns:
            tensor (Tensor): The new symplectic matrix
        """
        return self._backend.random_symplectic(num_modes)

    def new_orthogonal(self, num_modes: int) -> Tensor:
        return self._backend.random_orthogonal(num_modes)

    def numeric(self, tensor: Tensor) -> Tensor:
        return self._backend.asnumpy(tensor)

    def update_symplectic(self, symplectic_params: Sequence[Trainable], symplectic_grads: Sequence[Tensor], symplectic_lr: float):
        for S, dS_riemann in zip(symplectic_params, symplectic_grads):
            Y = self._backend.riemann_to_symplectic(S, dS_riemann)
            YT = self._backend.transpose(Y)
            new_value = self._backend.matmul(S, self._backend.expm(-symplectic_lr * YT) @ self._backend.expm(-symplectic_lr * (Y - YT)))
            self._backend.assign(S, new_value)

    def update_orthogonal(self, orthogonal_params: Sequence[Trainable], orthogonal_grads: Sequence[Tensor], orthogonal_lr: float):
        for O, dO_riemann in zip(orthogonal_params, orthogonal_grads):
            D = 0.5 * (dO_riemann - self._backend.matmul(self._backend.matmul(O, self._backend.transpose(dO_riemann)), O))
            new_value = self._backend.matmul(O, self._backend.expm(orthogonal_lr * self._backend.matmul(self._backend.transpose(D), O)))
            self._backend.assign(O, new_value)

    def update_euclidean(self, euclidean_params: Sequence[Trainable], euclidean_grads: Sequence[Tensor], euclidean_lr: float):
        # self._backend.update_euclidean(euclidean_params, euclidean_grads, euclidean_lr)
        self.euclidean_opt.lr = euclidean_lr
        self.euclidean_opt.apply_gradients(zip(euclidean_grads, euclidean_params))

    def extract_parameters(self, items: Sequence, kind: str) -> List[Trainable]:
        r"""
        Extracts the parameters of the given kind from the given items.
        Arguments:
            items (Sequence[Trainable]): The items to extract the parameters from
            kind (str): The kind of parameters to extract. Can be "symplectic", "orthogonal", or "euclidean".
        Returns:
            parameters (List[Trainable]): The extracted parameters
        """
        params_dict = dict()
        for item in items:
            try:
                for p in item.trainable_parameters[kind]:
                    if (hash := self._backend.hash_tensor(p)) not in params_dict:
                        params_dict[hash] = p
            except TypeError:  # NOTE: make sure hash_tensor raises a TypeError when the tensor is not hashable
                continue
        return list(params_dict.values())

    def loss_and_gradients(self, cost_fn: Callable, params: dict) -> Tuple[Tensor, Dict[str, Tensor]]:
        r"""
        Computes the loss and gradients of the cost function with respect to the parameters.
        The dictionary has three keys: "symplectic", "orthogonal", and "euclidean", to maintain
        the information of the different parameter types.

        Arguments:
            cost_fn (Callable): The cost function to be minimized
            params (dict): A dictionary of parameters to be optimized

        Returns:
            loss (float): The cost function of the current parameters
            gradients (dict): A dictionary of gradients of the cost function with respect to the parameters
        """
        loss, grads = self._backend.loss_and_gradients(cost_fn, params)  # delegate entirely to backend
        return loss, grads