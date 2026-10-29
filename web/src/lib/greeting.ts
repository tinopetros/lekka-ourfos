// Your first name: Workspace's, or the start of your email if it has none: tpetros@… → Tpetros
export function firstName(email: string, name?: string | null): string {
  if (name?.trim()) return name.trim().split(/\s+/)[0] ?? name;
  const local = email.split('@')[0]?.split(/[._-]/)[0] ?? email;
  return local.charAt(0).toUpperCase() + local.slice(1);
}
