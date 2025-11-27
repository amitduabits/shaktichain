import { useCallback } from 'react';
import PropTypes from 'prop-types';

/**
 * AgentMixSlider - A reusable component for 3 sliders that auto-balance to 100%
 * When one slider is adjusted, the others are proportionally adjusted to maintain sum of 100.
 */
function AgentMixSlider({ values, onChange, disabled }) {
  const { residential, commercial, fleet } = values;

  const handleSliderChange = useCallback((changedKey, newValue) => {
    const parsedValue = Math.min(100, Math.max(0, parseInt(newValue, 10) || 0));
    const keys = ['residential', 'commercial', 'fleet'];
    const otherKeys = keys.filter(k => k !== changedKey);

    // Calculate remaining percentage to distribute
    const remaining = 100 - parsedValue;

    // Get current values of other sliders
    const otherValues = otherKeys.map(k => values[k]);
    const otherTotal = otherValues.reduce((a, b) => a + b, 0);

    let newValues = { ...values, [changedKey]: parsedValue };

    if (otherTotal === 0) {
      // If other sliders are at 0, split remaining equally
      const splitValue = Math.floor(remaining / otherKeys.length);
      const remainder = remaining - (splitValue * otherKeys.length);
      otherKeys.forEach((key, i) => {
        newValues[key] = splitValue + (i === 0 ? remainder : 0);
      });
    } else {
      // Proportionally distribute remaining value
      let distributed = 0;
      otherKeys.forEach((key, index) => {
        if (index === otherKeys.length - 1) {
          // Last one gets the remainder to ensure sum is exactly 100
          newValues[key] = remaining - distributed;
        } else {
          const proportion = values[key] / otherTotal;
          const newVal = Math.round(remaining * proportion);
          newValues[key] = newVal;
          distributed += newVal;
        }
      });
    }

    // Ensure all values are non-negative
    Object.keys(newValues).forEach(key => {
      newValues[key] = Math.max(0, newValues[key]);
    });

    // Final adjustment to ensure sum is exactly 100
    const total = Object.values(newValues).reduce((a, b) => a + b, 0);
    if (total !== 100) {
      const diff = 100 - total;
      // Add difference to the largest non-changed value
      const adjustKey = otherKeys.reduce((maxKey, key) =>
        newValues[key] > newValues[maxKey] ? key : maxKey
      , otherKeys[0]);
      newValues[adjustKey] = Math.max(0, newValues[adjustKey] + diff);
    }

    onChange(newValues);
  }, [values, onChange]);

  const sliders = [
    { key: 'residential', label: 'Residential', color: '#10b981' },
    { key: 'commercial', label: 'Commercial', color: '#3b82f6' },
    { key: 'fleet', label: 'Fleet', color: '#f59e0b' },
  ];

  return (
    <div className="agent-mix-slider">
      <div className="agent-mix-header">
        <span className="agent-mix-title">Agent Mix</span>
        <span className="agent-mix-total">
          Total: {residential + commercial + fleet}%
        </span>
      </div>

      <div className="agent-mix-sliders">
        {sliders.map(({ key, label, color }) => (
          <div key={key} className="agent-mix-item">
            <div className="agent-mix-label-row">
              <span className="agent-mix-label">
                <span
                  className="agent-mix-dot"
                  style={{ backgroundColor: color }}
                />
                {label}
              </span>
              <span className="agent-mix-value">{values[key]}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={values[key]}
              onChange={(e) => handleSliderChange(key, e.target.value)}
              disabled={disabled}
              className="agent-mix-range"
              style={{
                '--slider-color': color,
                '--slider-progress': `${values[key]}%`,
              }}
            />
          </div>
        ))}
      </div>

      <div className="agent-mix-bar">
        <div
          className="agent-mix-segment residential"
          style={{ width: `${residential}%` }}
          title={`Residential: ${residential}%`}
        />
        <div
          className="agent-mix-segment commercial"
          style={{ width: `${commercial}%` }}
          title={`Commercial: ${commercial}%`}
        />
        <div
          className="agent-mix-segment fleet"
          style={{ width: `${fleet}%` }}
          title={`Fleet: ${fleet}%`}
        />
      </div>
    </div>
  );
}

AgentMixSlider.propTypes = {
  values: PropTypes.shape({
    residential: PropTypes.number.isRequired,
    commercial: PropTypes.number.isRequired,
    fleet: PropTypes.number.isRequired,
  }).isRequired,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

AgentMixSlider.defaultProps = {
  disabled: false,
};

export default AgentMixSlider;
