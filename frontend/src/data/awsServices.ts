import awsIconIndex from './awsIconIndex.json';

export interface AwsService {
  id: string;
  sourceIconId: string;
  type: string;
  category: string;
  categoryId: string;
  title: string;
  iconPath: string;
  description: string;
  provider: 'aws';
}

type AwsIconIndex = Record<string, string>;

const toTitleCase = (value: string): string =>
  value
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(' ');

const normalizeTitle = (iconId: string): string => {
  const stripped = iconId.replace(/^Arch_/, '').replace(/_/g, ' ').replace(/-/g, ' ');
  return toTitleCase(stripped.replace(/\s+/g, ' ').trim());
};

const deriveCategory = (iconPath: string): string => {
  if (!iconPath || typeof iconPath !== 'string') {
    return 'General';
  }
  const segments = iconPath.split('/');
  const archSegment = segments.find((segment) => /^Arch_/i.test(segment));
  if (!archSegment) {
    return 'General';
  }
  const cleaned = archSegment.replace(/^Arch_/i, '').replace(/_/g, ' ').replace(/-/g, ' ');
  return toTitleCase(cleaned || 'General');
};

const entries = Object.entries(awsIconIndex as AwsIconIndex)
  .filter(([, path]) => typeof path === 'string' && path.trim().length > 0)
  .filter(([, path]) => path.endsWith('.svg') || path.endsWith('.png'));

export const awsServices: AwsService[] = entries
  .map(([iconId, iconPath]) => {
    const category = deriveCategory(iconPath);
    const title = normalizeTitle(iconId);
  return {
      id: `aws:${iconId}`,
      sourceIconId: iconId,
      type: 'aws.service',
      category,
      categoryId: `aws:${category.toLowerCase().replace(/\s+/g, '-')}`,
      title,
      iconPath,
      description: `${title} AWS service`,
      provider: 'aws' as const,
      badges: ['AWS'],
    };
  })
  .sort((a, b) => a.title.localeCompare(b.title));

export const awsServiceCategories = Array.from(new Set(awsServices.map((service) => service.category))).sort(
  (a, b) => a.localeCompare(b),
);
