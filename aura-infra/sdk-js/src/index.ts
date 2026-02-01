/**
 * AURA Infra - JavaScript/TypeScript SDK
 * Financial infrastructure for AI agents
 * 
 * @example
 * ```typescript
 * import Aura from 'aura-infra';
 * 
 * const aura = new Aura('aura_your_api_key');
 * 
 * // Create a wallet
 * const wallet = await aura.wallets.create({
 *   agentId: 'my-bot',
 *   agentName: 'MyBot'
 * });
 * 
 * // Deposit funds
 * await wallet.deposit(100.00, 'revenue');
 * 
 * // Transfer
 * await wallet.transfer('wallet_xyz', 50.00, 'Payment');
 * ```
 */

export interface AuraConfig {
  apiKey: string;
  baseUrl?: string;
}

export interface WalletCreateParams {
  agentId: string;
  agentName: string;
  initialBalance?: number;
}

export interface WalletData {
  id: string;
  agentId: string;
  agentName: string;
  balance: number;
  currency: string;
  totalEarned: number;
  totalSpent: number;
  profit: number;
  createdAt: string;
}

export interface TransactionData {
  id: string;
  walletId: string;
  type: 'deposit' | 'withdrawal' | 'transfer' | 'fee';
  amount: number;
  currency: string;
  status: string;
  description: string;
  fromWalletId?: string;
  toWalletId?: string;
  createdAt: string;
  completedAt?: string;
}

export interface TransferResult {
  transaction: TransactionData;
  amountSent: number;
  fee: number;
  amountReceived: number;
  fromBalance: number;
  toBalance: number;
}

export interface AgentCreateParams {
  name: string;
  type: 'content_creator' | 'trader' | 'developer' | 'researcher' | 'assistant';
  description?: string;
}

export interface AgentData {
  id: string;
  name: string;
  type: string;
  description: string;
  reputationScore: number;
  isActive: boolean;
  createdAt: string;
  apiKey?: string; // Only on registration
  walletId?: string;
}

class AuraError extends Error {
  statusCode?: number;
  response?: any;

  constructor(message: string, statusCode?: number, response?: any) {
    super(message);
    this.name = 'AuraError';
    this.statusCode = statusCode;
    this.response = response;
  }
}

class Wallet {
  private aura: Aura;
  public id: string;
  public agentId: string;
  public agentName: string;
  public balance: number;
  public currency: string;
  public totalEarned: number;
  public totalSpent: number;
  public profit: number;
  public createdAt: string;

  constructor(aura: Aura, data: WalletData) {
    this.aura = aura;
    this.id = data.id;
    this.agentId = data.agentId;
    this.agentName = data.agentName;
    this.balance = data.balance;
    this.currency = data.currency;
    this.totalEarned = data.totalEarned;
    this.totalSpent = data.totalSpent;
    this.profit = data.profit;
    this.createdAt = data.createdAt;
  }

  async refresh(): Promise<Wallet> {
    const data = await this.aura.request<WalletData>('GET', `/wallets/${this.id}`);
    Object.assign(this, data);
    return this;
  }

  async deposit(amount: number, source: string, metadata?: Record<string, any>): Promise<TransactionData> {
    const result = await this.aura.request<{ transaction: TransactionData; new_balance: number }>(
      'POST',
      `/wallets/${this.id}/deposit`,
      { amount, source, metadata: metadata || {} }
    );
    this.balance = result.new_balance;
    return result.transaction;
  }

  async withdraw(amount: number, purpose: string, metadata?: Record<string, any>): Promise<TransactionData> {
    const result = await this.aura.request<{ transaction: TransactionData; new_balance: number }>(
      'POST',
      `/wallets/${this.id}/withdraw`,
      { amount, purpose, metadata: metadata || {} }
    );
    this.balance = result.new_balance;
    return result.transaction;
  }

  async transfer(toWalletId: string, amount: number, description?: string, metadata?: Record<string, any>): Promise<TransferResult> {
    const result = await this.aura.request<TransferResult>(
      'POST',
      `/wallets/${this.id}/transfer`,
      { to_wallet_id: toWalletId, amount, description: description || '', metadata: metadata || {} }
    );
    this.balance = result.fromBalance;
    return result;
  }

  async transactions(limit: number = 50): Promise<TransactionData[]> {
    const result = await this.aura.request<{ transactions: TransactionData[] }>(
      'GET',
      `/wallets/${this.id}/transactions?limit=${limit}`
    );
    return result.transactions;
  }
}

class WalletsResource {
  private aura: Aura;

  constructor(aura: Aura) {
    this.aura = aura;
  }

  async create(params: WalletCreateParams): Promise<Wallet> {
    const result = await this.aura.request<{ wallet: WalletData }>(
      'POST',
      '/wallets',
      {
        agent_id: params.agentId,
        agent_name: params.agentName,
        initial_balance: params.initialBalance || 0
      }
    );
    return new Wallet(this.aura, result.wallet);
  }

  async retrieve(walletId: string): Promise<Wallet> {
    const data = await this.aura.request<WalletData>('GET', `/wallets/${walletId}`);
    return new Wallet(this.aura, data);
  }

  async list(): Promise<Wallet[]> {
    const result = await this.aura.request<{ wallets: WalletData[] }>('GET', '/wallets');
    return result.wallets.map(w => new Wallet(this.aura, w));
  }
}

class AgentsResource {
  private aura: Aura;

  constructor(aura: Aura) {
    this.aura = aura;
  }

  async register(params: AgentCreateParams): Promise<AgentData> {
    const result = await this.aura.request<{ agent: AgentData; wallet: WalletData; api_key: string }>(
      'POST',
      '/agents/register',
      params
    );
    return {
      ...result.agent,
      apiKey: result.api_key,
      walletId: result.wallet.id
    };
  }

  async list(): Promise<AgentData[]> {
    const result = await this.aura.request<{ agents: AgentData[] }>('GET', '/agents');
    return result.agents;
  }

  async retrieve(agentId: string): Promise<AgentData> {
    return this.aura.request<AgentData>('GET', `/agents/${agentId}`);
  }
}

export class Aura {
  private apiKey: string;
  private baseUrl: string;
  
  public wallets: WalletsResource;
  public agents: AgentsResource;

  constructor(apiKey: string, config?: Partial<AuraConfig>) {
    this.apiKey = apiKey;
    this.baseUrl = config?.baseUrl || 'https://api.aura.nanilabs.dev';
    this.wallets = new WalletsResource(this);
    this.agents = new AgentsResource(this);
  }

  async request<T>(method: string, endpoint: string, body?: any): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      'Authorization': `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
      'X-AURA-SDK-Version': '0.1.0'
    };

    const options: RequestInit = {
      method,
      headers,
    };

    if (body && method !== 'GET') {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
      throw new AuraError(
        data.detail || data.error || 'Unknown error',
        response.status,
        data
      );
    }

    return data as T;
  }

  async getStats(): Promise<{
    totalAgents: number;
    totalWallets: number;
    totalTransactions: number;
    totalVolume: number;
    platformRevenue: number;
    totalBalanceHeld: number;
  }> {
    return this.request('GET', '/stats');
  }
}

export default Aura;
export { AuraError, Wallet };
