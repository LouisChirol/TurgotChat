'use client';

import { useState } from 'react';

export type DataSourceType = 'all' | 'particuliers' | 'professionnels';

interface DataSourceFilterProps {
  activeFilter: DataSourceType;
  onFilterChange: (filter: DataSourceType) => void;
  className?: string;
}

const DataSourceFilter = ({ activeFilter, onFilterChange, className = '' }: DataSourceFilterProps) => {
  const [isOpen, setIsOpen] = useState(false);

  const filters = [
    { id: 'all' as DataSourceType, label: 'Toutes les sources', icon: '🌐' },
    { id: 'particuliers' as DataSourceType, label: 'Particuliers', icon: '👤' },
    { id: 'professionnels' as DataSourceType, label: 'Professionnels', icon: '💼' },
  ];

  const activeFilterData = filters.find(f => f.id === activeFilter);

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
      >
        <span>{activeFilterData?.icon}</span>
        <span>{activeFilterData?.label}</span>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-48 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg z-10">
          <div className="py-1">
            {filters.map((filter) => (
              <button
                key={filter.id}
                onClick={() => {
                  onFilterChange(filter.id);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-2 text-sm text-left hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                  activeFilter === filter.id
                    ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                    : 'text-gray-700 dark:text-gray-200'
                }`}
              >
                <span className="text-lg">{filter.icon}</span>
                <span>{filter.label}</span>
                {activeFilter === filter.id && (
                  <svg className="w-4 h-4 ml-auto" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DataSourceFilter; 