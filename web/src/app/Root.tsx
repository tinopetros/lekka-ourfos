import { RecordSkeleton } from '@/components/Skeletons';
import { QueryState } from '@/components/QueryState';
import { useMe } from '@/lib/api/queries';
import { Layout } from './Layout';

// Nothing shows until we know who you are and where: the banner comes before any data
export function Root() {
  const { data: me, error } = useMe();
  return me ? (
    <Layout me={me} />
  ) : (
    <div className="p-6">
      <QueryState error={error} loading={<RecordSkeleton />} />
    </div>
  );
}
