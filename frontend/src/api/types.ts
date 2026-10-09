// Response shapes mirror the OpenAPI schema at /api/v1/schema. Money values arrive as
// decimal strings to avoid float rounding; they are formatted, never summed, in the browser.

export type Role = 'VIEWER' | 'ADMIN';

export interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  role: Role;
}

export interface TokenResponse {
  access: string;
  access_expires_in: number;
  user: User;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CustomerListItem {
  customer_id: string;
  full_name: string;
  email: string;
  city: string;
  state: string;
  kyc_status: 'VERIFIED' | 'PENDING' | 'REVIEW';
  segment: 'Mass' | 'Affluent' | 'HNI';
  risk_level: string | null;
  account_count: number;
  total_market_value: string | null;
}

export interface RiskProfile {
  risk_score: number;
  risk_level: 'Conservative' | 'Moderate' | 'Growth' | 'Aggressive';
  assessed_at: string;
  horizon_years: number;
  liquidity_need: 'LOW' | 'MEDIUM' | 'HIGH';
}

export interface Account {
  account_id: string;
  account_type: string;
  provider: string;
  opened_at: string;
  status: 'ACTIVE' | 'DORMANT' | 'CLOSED';
  base_currency: string;
}

export interface CustomerDetail extends Omit<CustomerListItem, 'risk_level' | 'account_count' | 'total_market_value'> {
  phone: string;
  date_of_birth: string;
  onboarded_at: string;
  latest_risk_profile: RiskProfile | null;
  accounts: Account[];
}

export interface Totals {
  market_value: string;
  cost_basis: string;
  unrealised_pnl: string;
  unrealised_pnl_pct: string | null;
  position_count: number;
}

export interface AccountTotals extends Totals {
  account_id: string;
  account_type: string;
  provider: string;
  status: Account['status'];
  snapshot_date: string | null;
}

export interface AllocationSlice {
  asset_class: string;
  market_value: string;
  weight_pct: string;
  position_count: number;
}

export interface Position {
  account_id: string;
  instrument_id: string;
  symbol: string;
  instrument_name: string;
  asset_class: string;
  quantity: string;
  avg_cost: string;
  last_price: string | null;
  cost_basis: string;
  market_value: string | null;
  unrealised_pnl: string | null;
  unrealised_pnl_pct: string | null;
  weight_pct: string | null;
  snapshot_date: string;
  price_date: string | null;
}

export interface Portfolio {
  customer_id: string;
  currency: string;
  as_of: { snapshot_date: string | null; price_date: string | null; unpriced_positions: number };
  totals: Totals;
  accounts: AccountTotals[];
  allocation: AllocationSlice[];
  positions: Position[];
}

export type TransactionType = 'BUY' | 'SELL' | 'DIVIDEND' | 'FEE';
export type TransactionStatus = 'SETTLED' | 'PENDING' | 'REVERSED';

export interface Transaction {
  transaction_id: string;
  account_id: string;
  instrument_id: string;
  symbol: string;
  instrument_name: string;
  transaction_type: TransactionType;
  trade_date: string;
  quantity: string;
  price: string;
  amount: string;
  status: TransactionStatus;
}

export interface Instrument {
  instrument_id: string;
  symbol: string;
  instrument_name: string;
  asset_class: string;
}

export const GOAL_TYPES = ['RETIREMENT', 'EDUCATION', 'EMERGENCY_FUND', 'HOME_PURCHASE', 'TRAVEL', 'WEALTH_CREATION'] as const;
export const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH'] as const;

export interface Goal {
  goal_id: string;
  customer_id: string;
  goal_type: (typeof GOAL_TYPES)[number];
  goal_name: string;
  target_amount: string;
  current_funded_amount: string;
  funded_pct: string;
  target_date: string;
  priority: (typeof PRIORITIES)[number];
  flags: ('OVERDUE' | 'OVERFUNDED')[];
  updated_at: string;
}

export type GoalInput = Pick<Goal, 'goal_type' | 'goal_name' | 'target_amount' | 'current_funded_amount' | 'target_date' | 'priority'>;

export interface StagedRow {
  row_number: number;
  record_key: string;
  outcome: 'INSERTED' | 'DUPLICATE' | 'REJECTED';
  errors: string[];
  warnings: string[];
  raw: Record<string, string>;
}

export interface ImportBatch {
  id: number;
  dataset: string;
  source: string;
  file_name: string;
  status: 'PROCESSING' | 'COMPLETED' | 'FAILED';
  total_rows: number;
  inserted_rows: number;
  duplicate_rows: number;
  rejected_rows: number;
  warning_rows: number;
  error_message: string;
  created_by: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface ImportResult extends ImportBatch {
  rejected: StagedRow[];
}
