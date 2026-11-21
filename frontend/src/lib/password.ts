/** Mirrors the backend password policy so users get immediate feedback. The backend remains authoritative. */
export function passwordIssues(pw: string): string[] {
  const issues: string[] = [];
  if (pw.length < 12) issues.push("at least 12 characters");
  const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
  if (classes < 3) issues.push("three of: lowercase, uppercase, digit, symbol");
  return issues;
}
