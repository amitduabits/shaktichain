import React, { useState, useEffect } from 'react';
import { useTransactions, TransactionStatus as TxStatus } from '../../providers/Web3Provider';
import { useAppMode } from '../../providers/Web3Provider';

interface TransactionStatusProps {
  showHistory?: boolean;
  maxHistory?: number;
  autoHide?: boolean;
  autoHideDelay?: number;
}

export function TransactionStatus({
  showHistory = true,
  maxHistory = 5,
  autoHide = true,
  autoHideDelay = 5000,
}: TransactionStatusProps) {
  const { isLiveMode } = useAppMode();
  const { transactions, latestTransaction, clearTransactions } = useTransactions();
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  // Show/hide based on latest transaction
  useEffect(() => {
    if (latestTransaction && !dismissed.has(latestTransaction.hash)) {
      setVisible(true);

      // Auto-hide after delay if enabled and transaction is complete
      if (autoHide && ['confirmed', 'failed'].includes(latestTransaction.status)) {
        const timer = setTimeout(() => {
          setDismissed((prev) => new Set([...prev, latestTransaction.hash]));
        }, autoHideDelay);
        return () => clearTimeout(timer);
      }
    }
  }, [latestTransaction, autoHide, autoHideDelay, dismissed]);

  // Don't show in simulation mode
  if (!isLiveMode) return null;

  // Filter visible transactions
  const visibleTransactions = transactions
    .filter((tx) => !dismissed.has(tx.hash))
    .slice(0, maxHistory);

  if (visibleTransactions.length === 0) return null;

  const dismiss = (hash: string) => {
    setDismissed((prev) => new Set([...prev, hash]));
  };

  const dismissAll = () => {
    setDismissed(new Set(transactions.map((tx) => tx.hash)));
  };

  return (
    <div className="transaction-status-container">
      {visibleTransactions.map((tx) => (
        <TransactionItem key={tx.hash} transaction={tx} onDismiss={dismiss} />
      ))}

      {showHistory && visibleTransactions.length > 1 && (
        <button className="dismiss-all-btn" onClick={dismissAll}>
          Dismiss All
        </button>
      )}
    </div>
  );
}

interface TransactionItemProps {
  transaction: {
    hash: string;
    status: TxStatus;
    description: string;
    timestamp: number;
    error?: string;
  };
  onDismiss: (hash: string) => void;
}

function TransactionItem({ transaction, onDismiss }: TransactionItemProps) {
  const { hash, status, description, error } = transaction;

  const statusConfig = {
    idle: { icon: '⏳', color: '#6b7280', text: 'Preparing' },
    pending: { icon: '🔄', color: '#f59e0b', text: 'Pending' },
    confirming: { icon: '⏳', color: '#3b82f6', text: 'Confirming' },
    confirmed: { icon: '✅', color: '#10b981', text: 'Confirmed' },
    failed: { icon: '❌', color: '#ef4444', text: 'Failed' },
  };

  const config = statusConfig[status];
  const shortHash = `${hash.slice(0, 6)}...${hash.slice(-4)}`;

  return (
    <div className={`transaction-item ${status}`}>
      <div className="tx-icon" style={{ color: config.color }}>
        {config.icon}
      </div>

      <div className="tx-content">
        <div className="tx-header">
          <span className="tx-description">{description}</span>
          <span className="tx-status" style={{ color: config.color }}>
            {config.text}
          </span>
        </div>

        <div className="tx-details">
          <a
            href={`https://polygonscan.com/tx/${hash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="tx-hash"
          >
            {shortHash}
          </a>

          {status === 'pending' && <LoadingSpinner />}
        </div>

        {error && <div className="tx-error">{error}</div>}
      </div>

      <button className="dismiss-btn" onClick={() => onDismiss(hash)}>
        ×
      </button>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="loading-spinner">
      <div className="spinner"></div>
    </div>
  );
}

// Toast notification component for quick feedback
interface ToastProps {
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  duration?: number;
  onClose?: () => void;
}

export function Toast({ message, type, duration = 3000, onClose }: ToastProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onClose?.();
    }, duration);
    return () => clearTimeout(timer);
  }, [duration, onClose]);

  if (!visible) return null;

  const typeConfig = {
    success: { icon: '✅', bg: 'rgba(16, 185, 129, 0.9)' },
    error: { icon: '❌', bg: 'rgba(239, 68, 68, 0.9)' },
    info: { icon: 'ℹ️', bg: 'rgba(59, 130, 246, 0.9)' },
    warning: { icon: '⚠️', bg: 'rgba(245, 158, 11, 0.9)' },
  };

  const config = typeConfig[type];

  return (
    <div className="toast" style={{ backgroundColor: config.bg }}>
      <span className="toast-icon">{config.icon}</span>
      <span className="toast-message">{message}</span>
      <button className="toast-close" onClick={() => setVisible(false)}>
        ×
      </button>
    </div>
  );
}

// Styles
const styles = `
.transaction-status-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  z-index: 1000;
  max-width: 400px;
}

.transaction-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: rgba(31, 41, 55, 0.95);
  border-radius: 12px;
  border: 1px solid rgba(75, 85, 99, 0.5);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.transaction-item.confirmed {
  border-color: rgba(16, 185, 129, 0.5);
}

.transaction-item.failed {
  border-color: rgba(239, 68, 68, 0.5);
}

.transaction-item.pending,
.transaction-item.confirming {
  border-color: rgba(245, 158, 11, 0.5);
}

.tx-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.tx-content {
  flex: 1;
  min-width: 0;
}

.tx-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.tx-description {
  font-size: 14px;
  font-weight: 500;
  color: #f3f4f6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tx-status {
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.tx-details {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tx-hash {
  font-size: 12px;
  color: #60a5fa;
  text-decoration: none;
  font-family: monospace;
}

.tx-hash:hover {
  text-decoration: underline;
}

.tx-error {
  margin-top: 8px;
  padding: 8px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 6px;
  font-size: 12px;
  color: #f87171;
}

.dismiss-btn {
  background: none;
  border: none;
  color: #6b7280;
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  transition: color 0.2s;
}

.dismiss-btn:hover {
  color: #9ca3af;
}

.dismiss-all-btn {
  padding: 8px 16px;
  background: rgba(75, 85, 99, 0.3);
  border: 1px solid rgba(75, 85, 99, 0.5);
  border-radius: 8px;
  color: #9ca3af;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.dismiss-all-btn:hover {
  background: rgba(75, 85, 99, 0.5);
  color: #f3f4f6;
}

.loading-spinner {
  display: inline-flex;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(245, 158, 11, 0.3);
  border-top-color: #f59e0b;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Toast styles */
.toast {
  position: fixed;
  top: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 1001;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.toast-icon {
  font-size: 16px;
}

.toast-message {
  flex: 1;
}

.toast-close {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.8);
  font-size: 18px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.toast-close:hover {
  color: white;
}
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);
}

export default TransactionStatus;
