import { Menu } from 'lucide-react';
import { Outlet } from 'react-router';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import type { Me } from '@/lib/api/types';
import { useUi } from '@/stores/ui';
import { EnvironmentBanner } from './EnvironmentBanner';
import { Navigation, Sidebar } from './Sidebar';

export function Layout({ me }: { me: Me }) {
  const { menuOpen, setMenuOpen } = useUi();
  return (
    <div className="flex h-dvh flex-col bg-background">
      <EnvironmentBanner environment={me.environment} />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center gap-3 border-b px-4 md:px-6">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Menu"
              onClick={() => {
                setMenuOpen(true);
              }}
            >
              <Menu />
            </Button>
            <span className="text-sm font-semibold md:hidden">OurFOS</span>
            <div className="ml-auto flex min-w-0 items-center gap-3 text-sm text-muted-foreground">
              <span className="truncate">{me.email}</span>
              <span className="hidden text-xs sm:inline" title="The build you're on">
                {me.version}
              </span>
            </div>
          </header>
          <main className="min-h-0 flex-1 overflow-auto p-4 md:p-6">
            <Outlet />
          </main>
        </div>
      </div>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetHeader className="border-b">
            <SheetTitle>OurFOS</SheetTitle>
          </SheetHeader>
          <Navigation />
        </SheetContent>
      </Sheet>
    </div>
  );
}
