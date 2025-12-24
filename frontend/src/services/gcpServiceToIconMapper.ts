// Mapping of common GCP service name variants to icon title tokens
// This file contains a small set of manual mappings and also augments the
// mapping at runtime by deriving easy aliases from the generated
// `src/data/gcpIconIndex.json` so we cover many title variants without
// manually typing hundreds of entries.

import gcpIconIndex from '@/data/gcpIconIndex.json';

const MANUAL_MAPPINGS: Record<string, string> = {
  'compute engine': 'Compute-Engine',
  'compute': 'Compute-Engine',
  'gce': 'Compute-Engine',
  'cloud storage': 'Cloud-Storage',
  'storage bucket': 'Cloud-Storage',
  'gcs': 'Cloud-Storage',
  'bigquery': 'BigQuery',
  'big query': 'BigQuery',
  'pubsub': 'PubSub',
  'pub/sub': 'PubSub',
  'cloud functions': 'Cloud-Functions',
  'functions': 'Cloud-Functions',
  'cloud run': 'Cloud-Run',
  'run': 'Cloud-Run',
  'cloud sql': 'Cloud-SQL',
  'sql': 'Cloud-SQL',
  'kubernetes engine': 'Google-Kubernetes-Engine',
  'gke': 'Google-Kubernetes-Engine',
  'vpc': 'Virtual-Private-Cloud',
  'virtual private cloud': 'Virtual-Private-Cloud',
  'iam': 'Identity-And-Access-Management',
  'identity and access management': 'Identity-And-Access-Management',
  'memorystore': 'Memorystore',
  'redis': 'Memorystore',
  'cloud spanner': 'Cloud-Spanner',
  'spanner': 'Cloud-Spanner',
  'datastore': 'Datastore',
  'firestore': 'Firestore',
  'cloud monitoring': 'Cloud-Monitoring',
  'stackdriver': 'Cloud-Monitoring',
};

// Build derived mappings from the generated icon index. For each title we
// create a few normalized alias keys (lowercased, with spaces instead of
// hyphens, and with/without common suffixes) that point back to the
// canonical title key used in the index.
const derived: Record<string, string> = {};
const index = (gcpIconIndex as Record<string, string>) || {};
Object.keys(index).forEach((title) => {
  // Title in the index is typically like "Cloud-Storage" or "BigQuery"
  const canonical = title; // keep as-is to match index keys

  const normal = title.toLowerCase();
  const spaces = normal.replace(/[-_]+/g, ' ');
  const compact = normal.replace(/[-_\s]+/g, '');
  const noCloud = spaces.replace(/^cloud\s+/i, '');
  const noApi = spaces.replace(/\sapi$/i, '');

  [normal, spaces, compact, noCloud, noApi].forEach((k) => {
    if (!k) return;
    if (!derived[k]) derived[k] = canonical;
  });
});

// Combine manual mappings first so they take precedence over derived ones.
const gcpServiceToIconMapper: Record<string, string> = {
  ...derived,
  ...Object.fromEntries(
    Object.entries(MANUAL_MAPPINGS).map(([k, v]) => [k.toLowerCase(), v])
  ),
};

export default gcpServiceToIconMapper;
