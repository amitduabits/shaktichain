"""Anomaly detection models for SHAKTI-CHAIN.

Implements:
- Isolation Forest for point anomalies
- LSTM Autoencoder for sequential patterns
- Graph Neural Network for network anomalies
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch not available - some models will be limited")

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("scikit-learn not available - Isolation Forest will use fallback")


class IsolationForestDetector:
    """Isolation Forest for point anomaly detection.

    Detects unusual individual trades based on features like:
    - Trade size
    - Price deviation
    - Trading frequency
    - Time of day
    """

    def __init__(
        self,
        n_estimators: int = 100,
        contamination: float = 0.1,
        max_samples: int = 256,
        random_state: int = 42,
    ):
        """Initialize Isolation Forest detector.

        Args:
            n_estimators: Number of trees
            contamination: Expected proportion of anomalies
            max_samples: Samples per tree
            random_state: Random seed
        """
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.max_samples = max_samples
        self.random_state = random_state

        self.scaler = StandardScaler() if HAS_SKLEARN else None
        self.model = None
        self.is_fitted = False

        self.feature_names = [
            'quantity',
            'price',
            'hour',
            'day_of_week',
            'trade_type',
            'price_deviation',
            'volume_ratio',
            'time_since_last_trade',
            'account_age_days',
            'account_trade_count',
        ]

    def fit(self, trades_df) -> 'IsolationForestDetector':
        """Fit the model on historical trade data.

        Args:
            trades_df: DataFrame with trade data

        Returns:
            self
        """
        if not HAS_SKLEARN:
            logger.warning("sklearn not available, using fallback detection")
            self.is_fitted = True
            return self

        # Extract features
        X = self._extract_features(trades_df)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Fit Isolation Forest
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            max_samples=min(self.max_samples, len(X_scaled)),
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.model.fit(X_scaled)
        self.is_fitted = True

        logger.info(f"Isolation Forest fitted on {len(X_scaled)} samples")
        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """Score samples for anomalies.

        Args:
            X: Feature array

        Returns:
            Anomaly scores (negative = more anomalous)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        if not HAS_SKLEARN or self.model is None:
            # Fallback scoring
            return self._fallback_score(X)

        X_scaled = self.scaler.transform(X)
        return self.model.score_samples(X_scaled)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict anomaly labels.

        Args:
            X: Feature array

        Returns:
            Labels: 1 for normal, -1 for anomaly
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        if not HAS_SKLEARN or self.model is None:
            scores = self._fallback_score(X)
            return np.where(scores < -0.5, -1, 1)

        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def _extract_features(self, trades_df) -> np.ndarray:
        """Extract feature matrix from trades DataFrame."""
        features = []

        for idx, row in trades_df.iterrows():
            feature_vec = [
                row.get('quantity', 0),
                row.get('price', 5),
                row.get('hour', 12),
                row.get('day_of_week', 0),
                1 if row.get('trade_type') == 'buy' else 0,
                row.get('price_deviation', 0),
                row.get('volume_ratio', 1),
                row.get('time_since_last_trade', 3600),
                row.get('account_age_days', 30),
                row.get('account_trade_count', 10),
            ]
            features.append(feature_vec)

        return np.array(features)

    def _fallback_score(self, X: np.ndarray) -> np.ndarray:
        """Fallback scoring using simple statistics."""
        scores = []
        for sample in X:
            # Simple z-score based anomaly
            z_score = np.abs(sample - np.mean(X, axis=0)) / (np.std(X, axis=0) + 1e-8)
            scores.append(-np.mean(z_score))
        return np.array(scores)

    def save(self, path: str):
        """Save model to file."""
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'config': {
                    'n_estimators': self.n_estimators,
                    'contamination': self.contamination,
                },
            }, f)

    @classmethod
    def load(cls, path: str) -> 'IsolationForestDetector':
        """Load model from file."""
        with open(path, 'rb') as f:
            data = pickle.load(f)

        detector = cls(
            n_estimators=data['config']['n_estimators'],
            contamination=data['config']['contamination'],
        )
        detector.model = data['model']
        detector.scaler = data['scaler']
        detector.is_fitted = True
        return detector


if HAS_TORCH:
    class LSTMAutoencoderModule(nn.Module):
        """LSTM Autoencoder neural network module."""

        def __init__(
            self,
            input_dim: int,
            hidden_dim: int = 64,
            latent_dim: int = 32,
            num_layers: int = 2,
            dropout: float = 0.2,
        ):
            super().__init__()

            self.input_dim = input_dim
            self.hidden_dim = hidden_dim
            self.latent_dim = latent_dim
            self.num_layers = num_layers

            # Encoder
            self.encoder_lstm = nn.LSTM(
                input_size=input_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0,
                bidirectional=True,
            )
            self.encoder_fc = nn.Linear(hidden_dim * 2, latent_dim)

            # Decoder
            self.decoder_fc = nn.Linear(latent_dim, hidden_dim * 2)
            self.decoder_lstm = nn.LSTM(
                input_size=hidden_dim * 2,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0,
            )
            self.output_fc = nn.Linear(hidden_dim, input_dim)

        def encode(self, x: torch.Tensor) -> torch.Tensor:
            """Encode sequence to latent space."""
            # x: (batch, seq_len, input_dim)
            lstm_out, (h_n, c_n) = self.encoder_lstm(x)

            # Use final hidden state
            h_n = torch.cat([h_n[-2], h_n[-1]], dim=1)  # (batch, hidden*2)
            latent = self.encoder_fc(h_n)  # (batch, latent_dim)
            return latent

        def decode(self, z: torch.Tensor, seq_len: int) -> torch.Tensor:
            """Decode latent vector to sequence."""
            # z: (batch, latent_dim)
            batch_size = z.size(0)

            # Expand latent to sequence
            decoder_input = self.decoder_fc(z)  # (batch, hidden*2)
            decoder_input = decoder_input.unsqueeze(1).repeat(1, seq_len, 1)  # (batch, seq_len, hidden*2)

            # Decode
            lstm_out, _ = self.decoder_lstm(decoder_input)  # (batch, seq_len, hidden)
            output = self.output_fc(lstm_out)  # (batch, seq_len, input_dim)

            return output

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            """Forward pass through autoencoder."""
            seq_len = x.size(1)
            latent = self.encode(x)
            reconstructed = self.decode(latent, seq_len)
            return reconstructed, latent


class LSTMAutoencoder:
    """LSTM Autoencoder for sequential anomaly detection.

    Learns normal trading patterns and flags sequences
    with high reconstruction error as anomalous.
    """

    def __init__(
        self,
        input_dim: int = 6,
        hidden_dim: int = 64,
        latent_dim: int = 32,
        num_layers: int = 2,
        seq_length: int = 24,
        dropout: float = 0.2,
        device: str = 'auto',
    ):
        """Initialize LSTM Autoencoder.

        Args:
            input_dim: Number of input features per timestep
            hidden_dim: LSTM hidden dimension
            latent_dim: Latent space dimension
            num_layers: Number of LSTM layers
            seq_length: Expected sequence length
            dropout: Dropout rate
            device: Device to use (auto, cpu, cuda)
        """
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.num_layers = num_layers
        self.seq_length = seq_length
        self.dropout = dropout

        # Set device
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        self.model = None
        self.scaler = StandardScaler() if HAS_SKLEARN else None
        self.threshold = None  # Reconstruction error threshold
        self.is_fitted = False

        if HAS_TORCH:
            self.model = LSTMAutoencoderModule(
                input_dim=input_dim,
                hidden_dim=hidden_dim,
                latent_dim=latent_dim,
                num_layers=num_layers,
                dropout=dropout,
            ).to(self.device)

    def fit(
        self,
        sequences: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 1e-3,
        val_split: float = 0.1,
        early_stopping_patience: int = 5,
    ) -> 'LSTMAutoencoder':
        """Train the autoencoder on normal sequences.

        Args:
            sequences: Array of shape (n_samples, seq_length, input_dim)
            epochs: Training epochs
            batch_size: Batch size
            learning_rate: Learning rate
            val_split: Validation split ratio
            early_stopping_patience: Patience for early stopping

        Returns:
            self
        """
        if not HAS_TORCH:
            logger.warning("PyTorch not available, using fallback")
            self.is_fitted = True
            return self

        # Normalize
        n_samples = sequences.shape[0]
        flat = sequences.reshape(-1, sequences.shape[-1])
        if self.scaler:
            flat_scaled = self.scaler.fit_transform(flat)
            sequences = flat_scaled.reshape(n_samples, -1, sequences.shape[-1])

        # Convert to tensor
        X = torch.FloatTensor(sequences).to(self.device)

        # Split train/val
        n_val = int(n_samples * val_split)
        indices = torch.randperm(n_samples)
        train_idx, val_idx = indices[n_val:], indices[:n_val]

        X_train, X_val = X[train_idx], X[val_idx]

        # Training setup
        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        criterion = nn.MSELoss()

        best_val_loss = float('inf')
        patience_counter = 0

        self.model.train()

        for epoch in range(epochs):
            # Mini-batch training
            train_losses = []
            for i in range(0, len(X_train), batch_size):
                batch = X_train[i:i+batch_size]

                optimizer.zero_grad()
                reconstructed, _ = self.model(batch)
                loss = criterion(reconstructed, batch)
                loss.backward()
                optimizer.step()

                train_losses.append(loss.item())

            # Validation
            self.model.eval()
            with torch.no_grad():
                val_reconstructed, _ = self.model(X_val)
                val_loss = criterion(val_reconstructed, X_val).item()
            self.model.train()

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs}, Train Loss: {np.mean(train_losses):.4f}, Val Loss: {val_loss:.4f}")

        # Calculate threshold on training data
        self.model.eval()
        with torch.no_grad():
            train_reconstructed, _ = self.model(X_train)
            errors = torch.mean((train_reconstructed - X_train) ** 2, dim=(1, 2)).cpu().numpy()
            self.threshold = np.percentile(errors, 95)  # 95th percentile

        self.is_fitted = True
        logger.info(f"LSTM Autoencoder fitted, threshold: {self.threshold:.4f}")
        return self

    def get_reconstruction_error(self, sequence: np.ndarray) -> float:
        """Calculate reconstruction error for a sequence.

        Args:
            sequence: Array of shape (seq_length, input_dim) or (1, seq_length, input_dim)

        Returns:
            Reconstruction error (MSE)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        if not HAS_TORCH:
            return self._fallback_error(sequence)

        # Ensure 3D
        if sequence.ndim == 2:
            sequence = sequence[np.newaxis, ...]

        # Normalize
        flat = sequence.reshape(-1, sequence.shape[-1])
        if self.scaler:
            flat_scaled = self.scaler.transform(flat)
            sequence = flat_scaled.reshape(1, -1, sequence.shape[-1])

        # Get reconstruction
        self.model.eval()
        with torch.no_grad():
            X = torch.FloatTensor(sequence).to(self.device)
            reconstructed, _ = self.model(X)
            error = torch.mean((reconstructed - X) ** 2).item()

        return error

    def score(self, sequence: np.ndarray) -> float:
        """Score a sequence for anomalies.

        Args:
            sequence: Input sequence

        Returns:
            Anomaly score (0-1, higher = more anomalous)
        """
        error = self.get_reconstruction_error(sequence)

        if self.threshold is None:
            return min(1.0, error)

        # Normalize by threshold
        return min(1.0, error / self.threshold)

    def _fallback_error(self, sequence: np.ndarray) -> float:
        """Fallback error calculation."""
        # Simple variance-based anomaly
        return np.var(sequence)

    def save(self, path: str):
        """Save model to file."""
        if HAS_TORCH:
            torch.save({
                'model_state': self.model.state_dict(),
                'scaler': self.scaler,
                'threshold': self.threshold,
                'config': {
                    'input_dim': self.input_dim,
                    'hidden_dim': self.hidden_dim,
                    'latent_dim': self.latent_dim,
                    'num_layers': self.num_layers,
                    'seq_length': self.seq_length,
                },
            }, path)

    @classmethod
    def load(cls, path: str) -> 'LSTMAutoencoder':
        """Load model from file."""
        if not HAS_TORCH:
            raise RuntimeError("PyTorch required to load model")

        data = torch.load(path)
        config = data['config']

        autoencoder = cls(
            input_dim=config['input_dim'],
            hidden_dim=config['hidden_dim'],
            latent_dim=config['latent_dim'],
            num_layers=config['num_layers'],
            seq_length=config['seq_length'],
        )
        autoencoder.model.load_state_dict(data['model_state'])
        autoencoder.scaler = data['scaler']
        autoencoder.threshold = data['threshold']
        autoencoder.is_fitted = True
        return autoencoder


if HAS_TORCH:
    class GraphConvLayer(nn.Module):
        """Simple Graph Convolution Layer."""

        def __init__(self, in_features: int, out_features: int):
            super().__init__()
            self.linear = nn.Linear(in_features, out_features)

        def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
            """Forward pass.

            Args:
                x: Node features (n_nodes, in_features)
                adj: Adjacency matrix (n_nodes, n_nodes)

            Returns:
                Updated node features (n_nodes, out_features)
            """
            # Normalize adjacency
            degree = adj.sum(dim=1, keepdim=True)
            adj_norm = adj / (degree + 1e-8)

            # Message passing
            out = torch.matmul(adj_norm, x)
            out = self.linear(out)
            return F.relu(out)


    class GraphAnomalyModule(nn.Module):
        """Graph Neural Network for anomaly detection."""

        def __init__(
            self,
            node_features: int,
            hidden_dim: int = 64,
            embedding_dim: int = 32,
            num_layers: int = 3,
        ):
            super().__init__()

            self.layers = nn.ModuleList()

            # Input layer
            self.layers.append(GraphConvLayer(node_features, hidden_dim))

            # Hidden layers
            for _ in range(num_layers - 2):
                self.layers.append(GraphConvLayer(hidden_dim, hidden_dim))

            # Output layer
            self.layers.append(GraphConvLayer(hidden_dim, embedding_dim))

            # Anomaly scoring head
            self.score_head = nn.Sequential(
                nn.Linear(embedding_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, 1),
                nn.Sigmoid(),
            )

        def forward(
            self,
            x: torch.Tensor,
            adj: torch.Tensor,
        ) -> Tuple[torch.Tensor, torch.Tensor]:
            """Forward pass.

            Args:
                x: Node features
                adj: Adjacency matrix

            Returns:
                (embeddings, anomaly_scores)
            """
            h = x
            for layer in self.layers:
                h = layer(h, adj)

            scores = self.score_head(h)
            return h, scores


class GraphAnomalyDetector:
    """Graph Neural Network for detecting network anomalies.

    Detects:
    - Coordinated trading patterns
    - Sybil account clusters
    - Unusual community structures
    """

    def __init__(
        self,
        node_features: int = 10,
        hidden_dim: int = 64,
        embedding_dim: int = 32,
        num_layers: int = 3,
        device: str = 'auto',
    ):
        """Initialize Graph Anomaly Detector.

        Args:
            node_features: Number of node features
            hidden_dim: Hidden dimension
            embedding_dim: Embedding dimension
            num_layers: Number of GNN layers
            device: Device to use
        """
        self.node_features = node_features
        self.hidden_dim = hidden_dim
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers

        if device == 'auto':
            self.device = torch.device('cuda' if HAS_TORCH and torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        self.model = None
        self.is_fitted = False

        if HAS_TORCH:
            self.model = GraphAnomalyModule(
                node_features=node_features,
                hidden_dim=hidden_dim,
                embedding_dim=embedding_dim,
                num_layers=num_layers,
            ).to(self.device)

    def fit(
        self,
        node_features: np.ndarray,
        adjacency_matrix: np.ndarray,
        labels: Optional[np.ndarray] = None,
        epochs: int = 100,
        learning_rate: float = 1e-3,
    ) -> 'GraphAnomalyDetector':
        """Train the GNN model.

        Args:
            node_features: Node feature matrix (n_nodes, n_features)
            adjacency_matrix: Adjacency matrix (n_nodes, n_nodes)
            labels: Optional anomaly labels for supervised learning
            epochs: Training epochs
            learning_rate: Learning rate

        Returns:
            self
        """
        if not HAS_TORCH:
            logger.warning("PyTorch not available")
            self.is_fitted = True
            return self

        X = torch.FloatTensor(node_features).to(self.device)
        A = torch.FloatTensor(adjacency_matrix).to(self.device)

        # Add self-loops
        A = A + torch.eye(A.size(0)).to(self.device)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)

        if labels is not None:
            # Supervised training
            Y = torch.FloatTensor(labels).unsqueeze(1).to(self.device)
            criterion = nn.BCELoss()

            self.model.train()
            for epoch in range(epochs):
                optimizer.zero_grad()
                _, scores = self.model(X, A)
                loss = criterion(scores, Y)
                loss.backward()
                optimizer.step()

                if (epoch + 1) % 20 == 0:
                    logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")
        else:
            # Unsupervised: reconstruction-based
            self.model.train()
            for epoch in range(epochs):
                optimizer.zero_grad()
                embeddings, _ = self.model(X, A)

                # Reconstruct adjacency from embeddings
                adj_pred = torch.sigmoid(torch.matmul(embeddings, embeddings.t()))
                loss = F.binary_cross_entropy(adj_pred, A)
                loss.backward()
                optimizer.step()

                if (epoch + 1) % 20 == 0:
                    logger.info(f"Epoch {epoch+1}/{epochs}, Reconstruction Loss: {loss.item():.4f}")

        self.is_fitted = True
        logger.info("Graph Anomaly Detector fitted")
        return self

    def score_node(
        self,
        node_id: str,
        graph_context: Dict[str, Any],
    ) -> float:
        """Score a single node for anomalies.

        Args:
            node_id: Node identifier
            graph_context: Graph context with features and adjacency

        Returns:
            Anomaly score (0-1)
        """
        if not self.is_fitted:
            return 0.0

        if not HAS_TORCH:
            return self._fallback_score(node_id, graph_context)

        X = torch.FloatTensor(graph_context['features']).to(self.device)
        A = torch.FloatTensor(graph_context['adjacency']).to(self.device)
        A = A + torch.eye(A.size(0)).to(self.device)

        node_idx = graph_context.get('node_mapping', {}).get(node_id, 0)

        self.model.eval()
        with torch.no_grad():
            _, scores = self.model(X, A)
            return scores[node_idx].item()

    def detect_sybil_score(
        self,
        account_id: str,
        network_graph: Any,
    ) -> float:
        """Detect Sybil account score.

        Args:
            account_id: Account identifier
            network_graph: Network graph object

        Returns:
            Sybil score (0-1)
        """
        if not self.is_fitted:
            return 0.0

        # Extract subgraph around account
        if hasattr(network_graph, 'get_neighbors'):
            neighbors = network_graph.get_neighbors(account_id, depth=2)
        else:
            return 0.0

        # Score based on community structure
        # High clustering with new accounts = suspicious
        new_account_ratio = sum(1 for n in neighbors if n.get('age_days', 100) < 7) / max(len(neighbors), 1)

        if new_account_ratio > 0.7:
            return min(1.0, new_account_ratio)

        return 0.0

    def get_embeddings(
        self,
        node_features: np.ndarray,
        adjacency_matrix: np.ndarray,
    ) -> np.ndarray:
        """Get node embeddings from the GNN.

        Args:
            node_features: Node features
            adjacency_matrix: Adjacency matrix

        Returns:
            Node embeddings
        """
        if not HAS_TORCH or not self.is_fitted:
            return node_features[:, :self.embedding_dim]

        X = torch.FloatTensor(node_features).to(self.device)
        A = torch.FloatTensor(adjacency_matrix).to(self.device)
        A = A + torch.eye(A.size(0)).to(self.device)

        self.model.eval()
        with torch.no_grad():
            embeddings, _ = self.model(X, A)
            return embeddings.cpu().numpy()

    def _fallback_score(
        self,
        node_id: str,
        graph_context: Dict[str, Any],
    ) -> float:
        """Fallback scoring without PyTorch."""
        # Simple degree-based anomaly
        adjacency = graph_context.get('adjacency', np.array([]))
        if len(adjacency) == 0:
            return 0.0

        node_idx = graph_context.get('node_mapping', {}).get(node_id, 0)
        degree = np.sum(adjacency[node_idx])
        avg_degree = np.mean(np.sum(adjacency, axis=1))

        # Unusually high or low degree
        if degree > avg_degree * 3 or (degree < avg_degree * 0.1 and avg_degree > 1):
            return min(1.0, abs(degree - avg_degree) / avg_degree)

        return 0.0

    def save(self, path: str):
        """Save model."""
        if HAS_TORCH and self.model is not None:
            torch.save({
                'model_state': self.model.state_dict(),
                'config': {
                    'node_features': self.node_features,
                    'hidden_dim': self.hidden_dim,
                    'embedding_dim': self.embedding_dim,
                    'num_layers': self.num_layers,
                },
            }, path)

    @classmethod
    def load(cls, path: str) -> 'GraphAnomalyDetector':
        """Load model."""
        if not HAS_TORCH:
            raise RuntimeError("PyTorch required")

        data = torch.load(path)
        config = data['config']

        detector = cls(**config)
        detector.model.load_state_dict(data['model_state'])
        detector.is_fitted = True
        return detector
