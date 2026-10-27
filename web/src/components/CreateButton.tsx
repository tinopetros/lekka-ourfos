import { Plus } from 'lucide-react';
import { Link } from 'react-router';
import { Button } from '@/components/ui/button';
import { useCan } from '@/lib/api/queries';
import { Tip } from './Tip';

// A new submission of a form, for whoever may submit it: nothing, for anyone else
export function CreateButton({ form, noun, size = 'sm' }: { form: string; noun: string; size?: 'sm' | 'xs' }) {
  const can = useCan();
  if (!can(`forms:${form}:submit`)) return null;
  return (
    <Tip label={`Start a new ${noun}`}>
      <Button variant="outline" size={size} asChild>
        <Link to={`/forms/${form}/new`}>
          <Plus /> New {noun}
        </Link>
      </Button>
    </Tip>
  );
}
