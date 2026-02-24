"""Training module for SHAKTI-CHAIN V2G platform."""

from .lightning_module import ForecastingLightningModule
from .quantile_loss import QuantileLoss, NormalizedQuantileLoss

try:
    from .tft_lightning_module import TFTLightningModule
except ImportError:
    TFTLightningModule = None

try:
    from .price_lightning_module import PricePredictorLightning, PriceLoss
except ImportError:
    PricePredictorLightning = None
    PriceLoss = None

__all__ = [
    "ForecastingLightningModule",
    "QuantileLoss",
    "NormalizedQuantileLoss",
]

if TFTLightningModule is not None:
    __all__.append("TFTLightningModule")
if PricePredictorLightning is not None:
    __all__.append("PricePredictorLightning")
if PriceLoss is not None:
    __all__.append("PriceLoss")
