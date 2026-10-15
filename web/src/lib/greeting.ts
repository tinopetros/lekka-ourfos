// The start of an email, as a name, until Workspace's directory gives us real ones: tpetros@… → Tpetros
export function firstName(email: string): string {
  const local = email.split('@')[0]?.split(/[._-]/)[0] ?? email;
  return local.charAt(0).toUpperCase() + local.slice(1);
}
