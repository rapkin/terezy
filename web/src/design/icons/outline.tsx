import type { ComponentType, ReactNode } from "react";

/**
 * The mockup's icon set: one 24-grid outline glyph per kind, at stroke 1.75.
 *
 * One weight and one grid, stated here once, because the same glyph is drawn at 16 px beside a
 * word and at 32 px inside a tile; two weights would make the small one disappear.
 */
function Outline({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export type IconComponent = ComponentType;

/** A coupon schedule: a document with dated rows. */
export function BondIcon() {
  return (
    <Outline>
      <path d="M5 3h11l3 3v15H5z" />
      <path d="M8 9h8M8 13h8M8 17h5" />
    </Outline>
  );
}

/** A pooled holding: units stacked into one vessel. */
export function FundIcon() {
  return (
    <Outline>
      <path d="M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z" />
      <path d="M4 7v10c0 1.7 3.6 3 8 3s8-1.3 8-3V7" />
      <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </Outline>
  );
}

/** Money that is not deployed: notes at rest. */
export function CashIcon() {
  return (
    <Outline>
      <rect x="3" y="6" width="18" height="12" rx="2" />
      <circle cx="12" cy="12" r="2.5" />
      <path d="M6 10v4M18 10v4" />
    </Outline>
  );
}

/** Something already owned rather than something to buy into. */
export function HeldAssetIcon() {
  return (
    <Outline>
      <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
      <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
    </Outline>
  );
}

/** Income arriving on a cadence. */
export function IncomeStreamIcon() {
  return (
    <Outline>
      <path d="M3 8h13a4 4 0 0 1 0 8H8" />
      <path d="M11 13l-3 3 3 3" />
    </Outline>
  );
}

/** Where money counts as spent: an endpoint the base currency reaches. */
export function SpendableEndpointIcon() {
  return (
    <Outline>
      <circle cx="12" cy="12" r="8" />
      <path d="M9 12l2 2 4-4" />
    </Outline>
  );
}

/** A bank account. */
export function BankIcon() {
  return (
    <Outline>
      <path d="M3 9l9-5 9 5" />
      <path d="M5 9v9M10 9v9M14 9v9M19 9v9" />
      <path d="M3 20h18" />
    </Outline>
  );
}

/** An exchange: one currency out, another in. */
export function ExchangeIcon() {
  return (
    <Outline>
      <path d="M4 8h13l-3-3M20 16H7l3 3" />
    </Outline>
  );
}

/** A broker: an order book. */
export function BrokerIcon() {
  return (
    <Outline>
      <path d="M4 20V4" />
      <path d="M4 20h16" />
      <path d="M8 16V11M12 16V7M16 16V13" />
    </Outline>
  );
}

/** A platform: an account held with a non-bank institution. */
export function PlatformIcon() {
  return (
    <Outline>
      <rect x="3" y="4" width="18" height="13" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </Outline>
  );
}

/** Payroll: where employment or contract income is paid from. */
export function PayrollIcon() {
  return (
    <Outline>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M3 12h18" />
    </Outline>
  );
}
