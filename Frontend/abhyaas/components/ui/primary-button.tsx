"use client";

import Link from "next/link";
import type { MouseEventHandler, ReactNode } from "react";

type PrimaryButtonProps = {
  children: ReactNode;
  href?: string;
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  className?: string;
  type?: "button" | "submit" | "reset";
  onClick?: MouseEventHandler<HTMLButtonElement>;
  ariaLabel?: string;
};

export default function PrimaryButton({
  children,
  href,
  size = "md",
  disabled = false,
  className = "",
  type = "button",
  onClick,
  ariaLabel,
}: PrimaryButtonProps) {
  const classes = `primary-button primary-button--${size}${className ? ` ${className}` : ""}`;

  if (href) {
    return (
      <Link
        href={href}
        className={classes}
        aria-label={ariaLabel}
        aria-disabled={disabled || undefined}
        tabIndex={disabled ? -1 : undefined}
        onClick={disabled ? (event) => event.preventDefault() : undefined}
      >
        {children}
      </Link>
    );
  }

  return <button type={type} className={classes} disabled={disabled} onClick={onClick} aria-label={ariaLabel}>{children}</button>;
}
