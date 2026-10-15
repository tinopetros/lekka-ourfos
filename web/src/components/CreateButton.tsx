import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tip } from './Tip';

// A stub until forms can be submitted here: it says so rather than doing nothing silently
export function CreateButton({ noun, size = 'sm' }: { noun: string; size?: 'sm' | 'xs' }) {
  return (
    <Tip label={`Creating a ${noun} here is coming soon`}>
      <Button variant="outline" size={size} aria-disabled="true" className="cursor-not-allowed">
        <Plus /> New
      </Button>
    </Tip>
  );
}
