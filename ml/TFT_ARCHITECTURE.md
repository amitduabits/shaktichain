# Temporal Fusion Transformer (TFT) Architecture

## Overview

The Temporal Fusion Transformer is a state-of-the-art deep learning architecture for multi-horizon time series forecasting with interpretability. It was introduced by Google Research in the paper ["Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting"](https://arxiv.org/abs/1912.09363).

### Key Features

- **Multi-horizon forecasting**: Predicts multiple time steps into the future
- **Quantile predictions**: Provides uncertainty estimates via quantile regression
- **Interpretability**: Variable selection and attention weights for explainability
- **Flexible inputs**: Handles static, known future, and observed inputs separately

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TEMPORAL FUSION TRANSFORMER                     │
└─────────────────────────────────────────────────────────────────────┘

INPUT LAYER
───────────
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Static Features  │  │ Historical Data  │  │  Future Data     │
│  (time-invariant)│  │  (past observed) │  │  (known future)  │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         │                     ├─────────────────────┤
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Static Embedding│  │ Observed Embed   │  │ Known Embed      │
└────────┬────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                    │                     │
         │                    │                     │
         ▼                    │                     │
┌─────────────────┐           │                     │
│ Variable Select │           │                     │
│ Network (Static)│           │                     │
└────────┬────────┘           │                     │
         │                    │                     │
         │  Context           │                     │
         └────────────────────┼─────────────────────┘
                              │
                              │
ENCODER SECTION              │
───────────────              │
                              │
         ┌────────────────────┴─────────────────────┐
         │                                           │
         ▼                                           ▼
┌─────────────────────┐                    ┌─────────────────────┐
│ Variable Selection  │                    │ Variable Selection  │
│ Network (Encoder)   │                    │ Network (Decoder)   │
│  - Observed inputs  │                    │  - Known inputs     │
│  - Known inputs     │                    │  - Future horizon   │
│  + Context (static) │                    │  + Context (static) │
└──────────┬──────────┘                    └──────────┬──────────┘
           │                                           │
           │ Selected features                         │ Selected features
           │ (encoder_length steps)                    │ (decoder_length steps)
           ▼                                           │
┌─────────────────────┐                                │
│   LSTM Encoder      │                                │
│  - 2 layers         │                                │
│  - Layer norm       │                                │
│  - Dropout          │                                │
└──────────┬──────────┘                                │
           │                                           │
           │ Encoder outputs + states                  │
           └───────────────────┬───────────────────────┘
                               │
                               │
DECODER SECTION                │
───────────────                │
                               │
                               ▼
                      ┌─────────────────────┐
                      │   LSTM Decoder      │
                      │  - 2 layers         │
                      │  - Layer norm       │
                      │  - Init from encoder│
                      └──────────┬──────────┘
                                 │
                                 │ Decoder outputs
                                 │ (decoder_length steps)
                                 ▼
                      ┌─────────────────────┐
                      │  Multi-Head         │
                      │  Self-Attention     │
                      │  (Interpretable)    │
                      │  + Encoder outputs  │
                      └──────────┬──────────┘
                                 │
                                 │ Attention outputs + weights
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │   Gated Add & Norm  │
                      └──────────┬──────────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │  Position-wise FFN  │
                      │  (2-layer MLP)      │
                      └──────────┬──────────┘
                                 │
                                 │
OUTPUT LAYER                     │
────────────                     │
                                 ▼
                      ┌─────────────────────┐
                      │  Quantile Outputs   │
                      │  - Separate heads   │
                      │  - Q10, Q50, Q90    │
                      └──────────┬──────────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │   Final Predictions │
                      │ (batch, 48h, 1, 3)  │
                      └─────────────────────┘

INTERPRETABILITY OUTPUTS
────────────────────────
┌──────────────────────┐  ┌──────────────────────┐
│ Variable Importance  │  │  Attention Weights   │
│  - Static features   │  │  - Temporal focus    │
│  - Encoder features  │  │  - Per time step     │
│  - Decoder features  │  │  - Per attention head│
└──────────────────────┘  └──────────────────────┘
```

## Core Components

### 1. Gated Residual Network (GRN)

The building block used throughout the architecture. Provides non-linear processing with gating mechanism.

```
Input x
  │
  ├─────────────────┐
  │                 │ (skip connection)
  ▼                 │
Linear(hidden)      │
  │                 │
  ▼                 │
ELU                 │
  │                 │
  ▼                 │
+ Context (optional)│
  │                 │
  ▼                 │
Linear(hidden)      │
  │                 │
  ▼                 │
ELU                 │
  │                 │
  ├────────┬────────┤
  │        │        │
  ▼        ▼        │
Gate    Output      │
  │        │        │
  └────────┤        │
           ▼        │
      Element-wise  │
      Multiply      │
           │        │
           ├────────┘
           │
           ▼
      Layer Norm
           │
           ▼
        Output
```

**Mathematical Formulation:**

```
GRN(x, c) = LayerNorm(skip + GLU(η₂(η₁(x) + c)))

where:
  η₁(x) = ELU(W₁x + b₁)
  η₂(h) = W₂h + b₂
  GLU(h) = σ(W_g h) ⊙ (W_o h)
  skip = W_s x  (if input_size ≠ output_size)
       = x      (if input_size = output_size)
```

### 2. Variable Selection Network (VSN)

Selects relevant features at each time step using learned attention weights.

```
Flattened Input (all variables)
  │
  ▼
GRN (produces selection weights)
  │
  ▼
Softmax (normalize weights)
  │
  ├──────────────────────────────┐
  │                              │
  ▼                              ▼
Weights                   Individual GRNs
(1 per variable)           (1 per variable)
  │                              │
  │                              │
  └──────────┬───────────────────┘
             │
             ▼
      Weighted Sum
             │
             ▼
      Selected Features
```

**Mathematical Formulation:**

```
VSN(ξ, c) = Σᵢ wᵢ · GRN_i(ξᵢ)

where:
  ξ = [ξ₁, ξ₂, ..., ξₙ]  (input variables)
  w = Softmax(GRN_flatten([ξ₁, ..., ξₙ], c))
  GRN_i processes each variable independently
```

### 3. LSTM Encoder-Decoder

Processes sequential information with layer normalization for stability.

```
Encoder Sequence
  │
  ▼
┌─────────────────┐
│  LSTM Layer 1   │
│  (bidirectional)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LSTM Layer 2   │
└────────┬────────┘
         │
         ▼
   Layer Norm
         │
         ├──────────────────┐
         │                  │
         │             Hidden States
         │                  │
         │                  │
Decoder Sequence            │
         │                  │
         ▼                  │
┌─────────────────┐         │
│  LSTM Layer 1   │◄────────┘
│  (init state)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LSTM Layer 2   │
└────────┬────────┘
         │
         ▼
   Layer Norm
         │
         ▼
   Decoder Output
```

### 4. Interpretable Multi-Head Attention

Standard scaled dot-product attention with additive head aggregation for interpretability.

```
Query (decoder)   Key (encoder)   Value (encoder)
      │                │                │
      ▼                ▼                ▼
   Linear           Linear           Linear
      │                │                │
      ├────────────────┼────────────────┤
      │                │                │
      ▼                ▼                ▼
   Split H heads   Split H heads   Split H heads
      │                │                │
      └────────┬───────┴────────┬───────┘
               │                │
               ▼                ▼
          Q·Kᵀ / √d_k      (attention scores)
               │
               ▼
           Softmax
               │
               ▼
          Attention Weights
               │
               ├──────────────┐
               │              │ (save for interpretability)
               ▼              ▼
            Score·V      Weights
               │
               ▼
          Concat Heads
               │
               ▼
            Linear
               │
               ▼
          Output
```

**Mathematical Formulation:**

```
Attention(Q, K, V) = softmax(QKᵀ/√d_k)V

MultiHead(Q, K, V) = Concat(head₁, ..., headₕ)W^O

where head_i = Attention(QW_i^Q, KW_i^K, VW_i^V)
```

### 5. Quantile Output Layer

Separate linear layers for each quantile prediction.

```
Hidden State
     │
     ├──────────┬──────────┬──────────┐
     │          │          │          │
     ▼          ▼          ▼          ▼
Linear(Q10) Linear(Q50) Linear(Q90) ...
     │          │          │          │
     └──────────┴──────────┴──────────┘
                    │
                    ▼
              Stack Quantiles
                    │
                    ▼
      (batch, time, output, num_quantiles)
```

## Data Flow Example

### Input Configuration

For SHAKTI-CHAIN load forecasting with:
- Encoder length: 168 hours (1 week)
- Decoder length: 48 hours (2 days)

```
Static Features (optional, not used in current config):
  - City ID
  - Prosumer type
  Shape: (batch, 0) - not used

Historical Observed (past data, not available in future):
  - load_mw_lag_1h
  - load_mw_lag_24h
  - temperature_c_delhi
  - price_inr_mwh_dam
  - humidity_pct_delhi
  Shape: (batch, 168, 5)

Historical Known (past data, available in future):
  - hour, hour_sin, hour_cos
  - day_of_week, day_of_week_sin, day_of_week_cos
  - is_weekend, is_holiday, is_peak_hour
  - month_sin
  Shape: (batch, 168, 10)

Future Known (future data, known at prediction time):
  - Same features as Historical Known
  - For the next 48 hours
  Shape: (batch, 48, 10)

Target:
  - load_mw (actual load to predict)
  Shape: (batch, 48, 1)
```

### Forward Pass Shapes

```python
# Input
static_covariates:     None or (32, 0)    # Batch of 32
historical_observed:   (32, 168, 5)       # 1 week history, 5 observed features
historical_known:      (32, 168, 10)      # 1 week history, 10 known features
future_known:          (32, 48, 10)       # 2 day future, 10 known features

# After embedding
static_embedded:       (32, 160)          # If static features exist
known_embedded:        (32, 216, 160)     # 168+48 time steps
observed_embedded:     (32, 168, 160)     # 168 time steps

# Variable selection
encoder_selected:      (32, 168, 160)     # Selected encoder features
decoder_selected:      (32, 48, 160)      # Selected decoder features

# LSTM outputs
encoder_output:        (32, 168, 160)     # Encoder hidden states
decoder_output:        (32, 48, 160)      # Decoder hidden states

# Attention
attention_output:      (32, 48, 160)      # Attended features
attention_weights:     (32, 4, 48, 168)   # 4 heads, attending to encoder

# Final output
predictions:           (32, 48, 1, 3)     # 3 quantiles [0.1, 0.5, 0.9]
```

## Training

### Loss Function

**Quantile Loss (Pinball Loss):**

```
L(y, ŷ, q) = max(q(y - ŷ), (q - 1)(y - ŷ))

Total Loss = (1/Q) Σ_q L(y, ŷ_q, q)
```

Where:
- y: True value
- ŷ_q: Predicted value at quantile q
- q: Quantile level (e.g., 0.1, 0.5, 0.9)

### Optimization

- **Optimizer**: Adam or AdamW
- **Learning Rate**: 1e-3 with ReduceLROnPlateau scheduler
- **Weight Decay**: 1e-5
- **Batch Size**: 32-128 depending on GPU memory
- **Epochs**: 50-100 with early stopping

### Metrics

1. **MAE (Mean Absolute Error)**: For median prediction
2. **RMSE (Root Mean Squared Error)**: For median prediction
3. **MAE per Quantile**: Separate MAE for Q10, Q50, Q90
4. **Coverage**: Percentage of actuals within [Q10, Q90] interval (should be ~80%)

## Interpretability

### Variable Importance

From Variable Selection Networks:

```python
# Static variable importance
static_weights: (batch, num_static_vars)

# Encoder variable importance (per time step)
encoder_weights: (batch, encoder_length, num_encoder_vars)

# Decoder variable importance (per time step)
decoder_weights: (batch, decoder_length, num_decoder_vars)
```

**Usage:**
```python
# Get average importance across batch and time
encoder_importance = encoder_weights.mean(dim=(0, 1))
# Shape: (num_encoder_vars,)
# Higher values = more important features
```

### Attention Weights

From Multi-Head Attention:

```python
attention_weights: (batch, num_heads, decoder_length, encoder_length)
```

**Usage:**
```python
# Average attention across heads and batch
avg_attention = attention_weights.mean(dim=(0, 1))
# Shape: (decoder_length, encoder_length)
# Shows which historical time steps the model focuses on
# for each prediction time step

# Example: For predicting hour 24 ahead, which past hours matter?
hour_24_attention = avg_attention[24, :]  # Shape: (168,)
# Shows attention to each of the 168 historical hours
```

## Model Configuration

### Small Model (for development/testing)

```yaml
architecture:
  hidden_size: 64
  lstm_layers: 1
  num_attention_heads: 2
  dropout: 0.1

sequence_lengths:
  encoder_length: 24    # 1 day
  decoder_length: 12    # 12 hours

# Parameters: ~200K
```

### Medium Model (recommended for production)

```yaml
architecture:
  hidden_size: 160
  lstm_layers: 2
  num_attention_heads: 4
  dropout: 0.1

sequence_lengths:
  encoder_length: 168   # 1 week
  decoder_length: 48    # 2 days

# Parameters: ~2M
```

### Large Model (for high-accuracy requirements)

```yaml
architecture:
  hidden_size: 256
  lstm_layers: 3
  num_attention_heads: 8
  dropout: 0.1

sequence_lengths:
  encoder_length: 336   # 2 weeks
  decoder_length: 72    # 3 days

# Parameters: ~8M
```

## Comparison with Other Architectures

| Feature | LSTM | Transformer | TFT |
|---------|------|-------------|-----|
| Multi-horizon | ✓ | ✓ | ✓ |
| Variable selection | ✗ | ✗ | ✓ |
| Attention | ✗ | ✓ | ✓ |
| Quantile prediction | ✗ | ✗ | ✓ |
| Interpretability | Limited | Attention only | Full |
| Training speed | Fast | Medium | Medium |
| Inference speed | Fast | Medium | Medium |
| Memory usage | Low | High | Medium |

## References

1. **Original Paper**: Lim, B., et al. (2020). "Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting." arXiv:1912.09363

2. **Implementation Reference**: Based on the PyTorch Forecasting library and Google Research's original implementation

3. **Related Papers**:
   - Attention Is All You Need (Vaswani et al., 2017)
   - Deep & Cross Network (Wang et al., 2017)
   - TabNet (Arik & Pfister, 2020)
