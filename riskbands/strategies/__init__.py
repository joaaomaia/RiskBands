from .categorical import CategoricalBinning
from .supervised import SupervisedBinning
from .unsupervised import UnsupervisedBinning


def get_strategy(name: str, **kwargs):
    if name == "supervised":
        return SupervisedBinning(**kwargs)
    elif name == "unsupervised":
        return UnsupervisedBinning(**kwargs)
    elif name == "categorical":
        return CategoricalBinning(**kwargs)
    else:
        raise ValueError(f"Unknown strategy '{name}'")


