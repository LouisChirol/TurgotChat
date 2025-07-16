'use client';

interface DataSourceIndicatorProps {
  sources: Array<{ url: string; title?: string; excerpt?: string }>;
  className?: string;
}

const DataSourceIndicator = ({ sources, className = '' }: DataSourceIndicatorProps) => {
  // Categorize sources
  const vosdroitsSources = sources.filter(s => s.url.includes('vosdroits'));
  const entreprendreSources = sources.filter(s => s.url.includes('entreprendre'));
  const otherSources = sources.filter(s => !s.url.includes('vosdroits') && !s.url.includes('entreprendre'));

  const hasMultipleTypes = (vosdroitsSources.length > 0 && entreprendreSources.length > 0) ||
                          (vosdroitsSources.length > 0 && otherSources.length > 0) ||
                          (entreprendreSources.length > 0 && otherSources.length > 0);

  if (sources.length === 0) return null;

  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      {vosdroitsSources.length > 0 && (
        <div className="flex items-center gap-1 px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 rounded-full text-xs font-medium">
          <span>👤</span>
          <span>Particuliers</span>
          {vosdroitsSources.length > 1 && (
            <span className="bg-blue-200 dark:bg-blue-800 rounded-full px-1.5 text-xs">
              {vosdroitsSources.length}
            </span>
          )}
        </div>
      )}
      
      {entreprendreSources.length > 0 && (
        <div className="flex items-center gap-1 px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 rounded-full text-xs font-medium">
          <span>💼</span>
          <span>Professionnels</span>
          {entreprendreSources.length > 1 && (
            <span className="bg-green-200 dark:bg-green-800 rounded-full px-1.5 text-xs">
              {entreprendreSources.length}
            </span>
          )}
        </div>
      )}
      
      {otherSources.length > 0 && (
        <div className="flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-full text-xs font-medium">
          <span>📄</span>
          <span>Autres</span>
          {otherSources.length > 1 && (
            <span className="bg-gray-200 dark:bg-gray-600 rounded-full px-1.5 text-xs">
              {otherSources.length}
            </span>
          )}
        </div>
      )}
      
      {hasMultipleTypes && (
        <div className="flex items-center gap-1 px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-200 rounded-full text-xs font-medium">
          <span>🔗</span>
          <span>Sources mixtes</span>
        </div>
      )}
    </div>
  );
};

export default DataSourceIndicator; 