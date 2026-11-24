import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import StatusBadge from './components/StatusBadge';
import MetricCard from './components/MetricCard';
import Alert from './components/Alert';
import { Wallet } from 'lucide-react';

describe('Frontend Component Tests', () => {
  it('renders StatusBadge correctly for various states', () => {
    const { rerender } = render(<StatusBadge status="SUCCESS" />);
    expect(screen.getByText('Success')).toBeInTheDocument();

    rerender(<StatusBadge status="FLAGGED" />);
    expect(screen.getByText('Flagged Hold')).toBeInTheDocument();

    rerender(<StatusBadge status="FROZEN" />);
    expect(screen.getByText('Frozen')).toBeInTheDocument();

    rerender(<StatusBadge status="APPROVED" />);
    expect(screen.getByText('Approved')).toBeInTheDocument();
  });

  it('renders MetricCard with formatted financial values', () => {
    render(
      <MetricCard
        title="Available Balance"
        value="₹74,500.00"
        subtitle="INR Currency"
        icon={Wallet}
        color="emerald"
      />
    );
    expect(screen.getByText('Available Balance')).toBeInTheDocument();
    expect(screen.getByText('₹74,500.00')).toBeInTheDocument();
    expect(screen.getByText('INR Currency')).toBeInTheDocument();
  });

  it('renders Alert component with error and success messages', () => {
    const { rerender } = render(<Alert type="error" message="Insufficient funds in account" />);
    expect(screen.getByText('Insufficient funds in account')).toBeInTheDocument();

    rerender(<Alert type="success" message="Transfer completed successfully" />);
    expect(screen.getByText('Transfer completed successfully')).toBeInTheDocument();
  });
});

