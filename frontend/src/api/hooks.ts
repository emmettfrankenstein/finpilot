import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './client';
import type {
  CustomerDetail,
  CustomerListItem,
  Goal,
  GoalInput,
  ImportBatch,
  ImportResult,
  Instrument,
  Paginated,
  Portfolio,
  StagedRow,
  Transaction,
} from './types';

export interface CustomerFilters {
  search?: string;
  kyc_status?: string;
  segment?: string;
  ordering?: string;
  page?: number;
}

export function useCustomers(filters: CustomerFilters) {
  return useQuery({
    queryKey: ['customers', filters],
    queryFn: ({ signal }) => api<Paginated<CustomerListItem>>('/customers', { query: { ...filters }, signal }),
    placeholderData: keepPreviousData,
  });
}

export function useCustomer(customerId: string) {
  return useQuery({
    queryKey: ['customer', customerId],
    queryFn: ({ signal }) => api<CustomerDetail>(`/customers/${encodeURIComponent(customerId)}`, { signal }),
  });
}

export function usePortfolio(customerId: string) {
  return useQuery({
    queryKey: ['portfolio', customerId],
    queryFn: ({ signal }) => api<Portfolio>(`/customers/${encodeURIComponent(customerId)}/portfolio`, { signal }),
  });
}

export interface TransactionFilters {
  date_from?: string;
  date_to?: string;
  account?: string;
  instrument?: string;
  type?: string[];
  status?: string[];
  ordering?: string;
  page?: number;
  page_size?: number;
}

export function useTransactions(customerId: string, filters: TransactionFilters) {
  return useQuery({
    queryKey: ['transactions', customerId, filters],
    queryFn: ({ signal }) =>
      api<Paginated<Transaction>>(`/customers/${encodeURIComponent(customerId)}/transactions`, {
        query: { ...filters },
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

export function useInstruments() {
  return useQuery({
    queryKey: ['instruments'],
    queryFn: ({ signal }) => api<Instrument[]>('/instruments', { signal }),
    staleTime: 60 * 60 * 1000,
  });
}

export function useGoals(customerId: string) {
  return useQuery({
    queryKey: ['goals', customerId],
    queryFn: ({ signal }) => api<Goal[]>(`/customers/${encodeURIComponent(customerId)}/goals`, { signal }),
  });
}

export function useSaveGoal(customerId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ goalId, data }: { goalId?: string; data: Partial<GoalInput> }) =>
      goalId
        ? api<Goal>(`/goals/${encodeURIComponent(goalId)}`, { method: 'PATCH', json: data })
        : api<Goal>(`/customers/${encodeURIComponent(customerId)}/goals`, { method: 'POST', json: data }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['goals', customerId] }),
  });
}

export function useImportBatches() {
  return useQuery({
    queryKey: ['imports'],
    queryFn: ({ signal }) => api<Paginated<ImportBatch>>('/admin/imports', { query: { page_size: 10 }, signal }),
  });
}

export function useImportRows(batchId: number | null, outcome: string, page: number) {
  return useQuery({
    queryKey: ['import-rows', batchId, outcome, page],
    queryFn: ({ signal }) =>
      api<Paginated<StagedRow>>(`/admin/imports/${batchId}/rows`, { query: { outcome, page }, signal }),
    enabled: batchId !== null,
    placeholderData: keepPreviousData,
  });
}

export function useUploadImport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ dataset, file }: { dataset: string; file: File }) => {
      const body = new FormData();
      body.append('file', file);
      return api<ImportResult>(`/admin/imports/${dataset}`, { method: 'POST', body });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['imports'] });
      client.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
}
