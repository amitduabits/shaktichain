import { TokenBalance, StakingPanel } from '../components/web3';
import { useDemoLedger } from '../context/DemoLedgerContext';

export function SettlementPage() {
  const { ledger } = useDemoLedger();
  return (
    <section className="role-panel">
      <h2 className="page-title">Settlement</h2>
      <TokenBalance variant="detailed" showVotingPower showTotalSupply />
      <StakingPanel
        simulatedData={{
          stakedAmount: String(ledger?.account?.stakedAmount ?? 0),
          pendingRewards: String(ledger?.account?.pendingRewards ?? 0),
          apr: Number(ledger?.staking?.apr ?? 0),
          totalStaked: String(ledger?.staking?.totalStaked ?? 0),
        }}
      />
    </section>
  );
}

export default SettlementPage;
