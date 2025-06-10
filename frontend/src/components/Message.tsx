'use client';

import Image from 'next/image';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Source {
  url: string;
  title: string;
  excerpt: string;
}

interface MessageProps {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  secondarySources?: Source[];
  isError?: boolean;
}

const Message = ({ role, content, sources = [], secondarySources = [], isError = false }: MessageProps) => {
  const isUser = role === 'user';

  const getAvatarSrc = () => {
    if (isError || content.includes("Désolé, une erreur est survenue. Veuillez réessayer.")) {
      return '/colbert_sorry.png';
    }
    return '/colbert_avatar.png';
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} gap-3`}>
      {!isUser && (
        <div className="w-12 h-12 rounded-full overflow-hidden flex-shrink-0">
          <Image
            src={getAvatarSrc()}
            alt="Colbert Assistant"
            width={48}
            height={48}
            className="w-full h-full object-cover"
          />
        </div>
      )}
      <div
        className={`max-w-[80%] rounded-lg p-4 ${
          isUser
            ? 'bg-blue-500 text-white'
            : isError || content.includes("Désolé, une erreur est survenue. Veuillez réessayer.")
            ? 'bg-red-100 text-red-800'
            : 'bg-gray-100 text-gray-800'
        }`}
      >
        <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : 'prose-gray'}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Style links
              a: ({ node, ...props }) => (
                <a
                  {...props}
                  className={`${
                    isUser
                      ? 'text-blue-200 hover:text-white'
                      : 'text-blue-600 hover:text-blue-800'
                  } underline transition-colors`}
                  target="_blank"
                  rel="noopener noreferrer"
                />
              ),
              // Style lists
              ul: ({ node, ...props }) => (
                <ul {...props} className={`list-disc pl-4 space-y-1 ${isUser ? 'text-white' : 'text-gray-800'}`} />
              ),
              ol: ({ node, ...props }) => (
                <ol {...props} className={`list-decimal pl-4 space-y-1 ${isUser ? 'text-white' : 'text-gray-800'}`} />
              ),
              // Style paragraphs
              p: ({ node, ...props }) => (
                <p {...props} className={`mb-2 ${isUser ? 'text-white' : 'text-gray-800'}`} />
              ),
              // Style headings
              h1: ({ node, ...props }) => (
                <h1 {...props} className={`text-xl font-bold mb-2 ${isUser ? 'text-white' : 'text-gray-900'}`} />
              ),
              h2: ({ node, ...props }) => (
                <h2 {...props} className={`text-lg font-bold mb-2 ${isUser ? 'text-white' : 'text-gray-900'}`} />
              ),
              h3: ({ node, ...props }) => (
                <h3 {...props} className={`text-base font-bold mb-2 ${isUser ? 'text-white' : 'text-gray-900'}`} />
              ),
              // Style code blocks
              code: ({ node, inline, ...props }: { node?: any; inline?: boolean } & React.HTMLAttributes<HTMLElement>) => (
                inline ? (
                  <code {...props} className={`${isUser ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'} rounded px-1 py-0.5`} />
                ) : (
                  <code {...props} className={`block ${isUser ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'} rounded p-2 my-2`} />
                )
              ),
            }}
          >
            {content}
          </ReactMarkdown>
        </div>
        {sources.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <details className="group">
              <summary className="flex items-center gap-2 cursor-pointer text-sm font-semibold text-gray-900 hover:text-blue-600 transition-colors">
                <svg
                  className="w-4 h-4 transform group-open:rotate-90 transition-transform"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Sources principales ({sources.length})
              </summary>
              <ul className="mt-2 space-y-3 pl-6">
                {sources.map((source, index) => (
                  <li key={index} className="text-sm break-words">
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 hover:underline truncate block max-w-full"
                      title={source.url}
                    >
                      {source.url.length > 60 ? `${source.url.substring(0, 60)}...` : source.url}
                    </a>
                    {source.excerpt && (
                      <p className="text-gray-600 mt-1 break-words text-sm">{source.excerpt}</p>
                    )}
                  </li>
                ))}
              </ul>
            </details>

            {secondarySources.length > 0 && (
              <details className="group mt-3">
                <summary className="flex items-center gap-2 cursor-pointer text-sm font-semibold text-gray-700 hover:text-blue-600 transition-colors">
                  <svg
                    className="w-4 h-4 transform group-open:rotate-90 transition-transform"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                  Sources complémentaires ({secondarySources.length})
                </summary>
                <ul className="mt-2 space-y-3 pl-6">
                  {secondarySources.map((source, index) => (
                    <li key={index} className="text-sm break-words">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-500 hover:text-blue-700 hover:underline truncate block max-w-full"
                        title={source.url}
                      >
                        {source.url.length > 60 ? `${source.url.substring(0, 60)}...` : source.url}
                      </a>
                      {source.excerpt && (
                        <p className="text-gray-500 mt-1 break-words text-sm">{source.excerpt}</p>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Message; 