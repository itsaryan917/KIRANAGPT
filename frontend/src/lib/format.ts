/**
 * Format a number as Indian currency (₹1,00,000)
 */
export function formatINR(amount: number): string {
  if (isNaN(amount)) return '₹0';
  
  // 🔥 Intelligently round large estimates to the nearest 100
  const roundedAmount = amount > 1000 ? Math.round(amount / 100) * 100 : amount;
  
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(roundedAmount);
  return formatted;
}

/**
 * Format a date string as "12 Jan 2025, 3:42 PM"
 */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Format a 0-1 confidence value as "71.2%"
 */
export function formatConfidence(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * Format a 0-100 percentage with 1 decimal
 */
export function formatPct(value: number): string {
  return `${value.toFixed(1)}%`;
}
