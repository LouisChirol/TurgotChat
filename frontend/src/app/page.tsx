'use client';

import AppDrawer from '@/components/AppDrawer';
import ChatInput from '@/components/ChatInput';
import ChatInterface from '@/components/ChatInterface';
import ConfirmationModal from '@/components/ConfirmationModal';
import DataSourceFilter, { DataSourceType } from '@/components/DataSourceFilter';
import { DarkModeButton, DisclaimerModal, InfoButton } from '@/components/Disclaimer';
import SupportButton from '@/components/SupportButton';
import { clearSession, sendMessage } from '@/services/api';
import { getSessionId } from '@/services/session';
import { Bars3Icon } from '@heroicons/react/24/outline';
import Image from 'next/image';
import { useEffect, useMemo, useState } from 'react';

export default function Home() {
  const [messages, setMessages] = useState([
    {
      id: '1',
      content: 'Bonjour ! Je suis Turgot, votre assistant pour les démarches administratives françaises. 🏛️\n\nJe peux vous aider avec :\n\n- **👤 Les droits des particuliers** ([vosdroits.service-public.fr](https://vosdroits.service-public.fr))\n- **💼 Les démarches pour professionnels** ([entreprendre.service-public.fr](https://entreprendre.service-public.fr))\n\nUtilisez le filtre en haut à droite pour afficher uniquement les informations qui vous concernent !\n\nComment puis-je vous aider aujourd\'hui ?',
      isUser: false,
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [isDisclaimerOpen, setIsDisclaimerOpen] = useState(false);
  const [dataSourceFilter, setDataSourceFilter] = useState<DataSourceType>('all');

  // Clear session history on page load/refresh for privacy
  useEffect(() => {
    const clearHistoryOnLoad = async () => {
      try {
        const sessionId = getSessionId();
        if (sessionId) {
          // Clear the previous session from backend
          await clearSession();
        }
        // Generate a new session ID
        const newSessionId = crypto.randomUUID();
        localStorage.setItem('turgot_session_id', newSessionId);
        localStorage.setItem('turgot_last_activity', Date.now().toString());
      } catch (error) {
        console.error('Error clearing history on load:', error);
      }
    };
    
    clearHistoryOnLoad();
  }, []);

  // Filter messages based on data source filter
  const filteredMessages = useMemo(() => {
    if (dataSourceFilter === 'all') return messages;

    return messages.map(message => {
      if (message.isUser) return message;

      // Extract sources from message content
      const sourceMatches = message.content.match(/\[([^\]]+)\]\(([^)]+)\)/g);
      const sources = sourceMatches ? sourceMatches.map(match => {
        const [, title, url] = match.match(/\[([^\]]+)\]\(([^)]+)\)/) || [];
        return { url, title: title || url };
      }) : [];

      // Check if message has sources matching the filter
      const hasMatchingSources = sources.some(source => {
        if (dataSourceFilter === 'particuliers') {
          return source.url.includes('vosdroits');
        } else if (dataSourceFilter === 'professionnels') {
          return source.url.includes('entreprendre');
        }
        return false;
      });

      // If no sources or no matching sources, hide the message
      if (sources.length === 0 || !hasMatchingSources) {
        return { ...message, content: '**Message filtré** - Cette réponse ne contient pas de sources pour le type sélectionné.' };
      }

      return message;
    });
  }, [messages, dataSourceFilter]);

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return;

    const newMessage = {
      id: Date.now().toString(),
      content: message,
      isUser: true,
    };

    setMessages((prev) => [...prev, newMessage]);
    setIsLoading(true);

    try {
      const response = await sendMessage(message);
      const aiMessage = {
        id: (Date.now() + 1).toString(),
        content: response.answer,
        isUser: false,
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        content: 'Désolé, une erreur est survenue. Veuillez réessayer.',
        isUser: false,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportPDF = async () => {
    const sessionId = getSessionId();
    if (!sessionId) {
      console.error('No session ID found');
      return;
    }

    setIsExporting(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const requestUrl = `${apiUrl}/generate-pdf`;
      
      // First, request PDF generation
      const response = await fetch(requestUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ session_id: sessionId }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Response error text:', errorText);
        throw new Error(`Failed to export PDF: ${response.status} ${response.statusText}`);
      }

      // Get the PDF URL from the JSON response
      const data = await response.json();
      const pdfUrl = data.pdf_url;
      
      if (!pdfUrl) {
        throw new Error('No PDF URL received');
      }

      const fullPdfUrl = `${apiUrl}${pdfUrl}`;

      // Download the actual PDF file
      const pdfResponse = await fetch(fullPdfUrl);
      
      if (!pdfResponse.ok) {
        throw new Error('Failed to download PDF');
      }

      // Get the blob from the PDF response
      const blob = await pdfResponse.blob();
      
      // Create a download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `turgot_chat_${sessionId}.pdf`;
      document.body.appendChild(a);
      a.click();
      
      // Cleanup
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error exporting PDF:', error);
      alert('Une erreur est survenue lors de l\'export du PDF. Veuillez réessayer.');
    } finally {
      setIsExporting(false);
    }
  };

  const handleReset = async () => {
    try {
      // Clear the current session from the backend
      await clearSession();
      
      // Generate a new session ID to ensure complete privacy
      const newSessionId = crypto.randomUUID();
      localStorage.setItem('turgot_session_id', newSessionId);
      localStorage.setItem('turgot_last_activity', Date.now().toString());
      
      // Reset the UI to show only the welcome message
      setMessages([
        {
          id: '1',
          content: 'Bonjour ! Je suis Turgot, votre assistant pour les démarches administratives françaises. 🏛️\n\nJe peux vous aider avec :\n\n- **👤 Les droits des particuliers** ([vosdroits.service-public.fr](https://vosdroits.service-public.fr))\n- **💼 Les démarches pour professionnels** ([entreprendre.service-public.fr](https://entreprendre.service-public.fr))\n\nUtilisez le filtre en haut à droite pour afficher uniquement les informations qui vous concernent !\n\nComment puis-je vous aider aujourd\'hui ?',
          isUser: false,
        },
      ]);
      setIsResetModalOpen(false);
    } catch (error) {
      console.error('Error resetting session:', error);
      // You might want to show an error message to the user here
    }
  };

  const handleSupport = () => {
    window.open('https://www.buymeacoffee.com/louischirol', '_blank');
  };
  const handleGitHub = () => {
    window.open('https://github.com/LouisChirol/TurgotChat', '_blank');
  };

  return (
    <main className="flex flex-col h-[100dvh]">
      <header className="shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 transition-colors duration-200">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Image
                src="/turgot_v2.png"
                alt="Turgot Assistant"
                width={60}
                height={60}
                className="rounded-full"
              />
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold dark:text-white">Turgot</h1>
                  <div className="w-6 h-4 flex overflow-hidden rounded-sm shadow-sm">
                    <div className="flex-1 bg-blue-600"></div>
                    <div className="flex-1 bg-white"></div>
                    <div className="flex-1 bg-red-600"></div>
                  </div>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-300">Votre assistant administratif</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <DataSourceFilter 
                activeFilter={dataSourceFilter}
                onFilterChange={setDataSourceFilter}
                className="hidden sm:block"
              />
              <InfoButton onClick={() => setIsDisclaimerOpen(true)} />
              <DarkModeButton />
              <button
                onClick={() => setIsDrawerOpen(true)}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label="Ouvrir le menu"
              >
                <Bars3Icon className="h-7 w-7 text-gray-700 dark:text-gray-200" />
              </button>
            </div>
          </div>
          {/* Mobile data source filter */}
          <div className="mt-3 sm:hidden">
            <DataSourceFilter 
              activeFilter={dataSourceFilter}
              onFilterChange={setDataSourceFilter}
            />
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <ChatInterface messages={filteredMessages} isLoading={isLoading} />
          </div>
        </div>

        <SupportButton />

        <div className="shrink-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 pb-safe transition-colors duration-200">
          <div className="h-1 flex max-w-4xl mx-auto">
            <div className="flex-1 bg-blue-600"></div>
            <div className="flex-1 bg-white"></div>
            <div className="flex-1 bg-red-600"></div>
          </div>
          <div className="max-w-4xl mx-auto px-4 py-4">
            <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
          </div>
        </div>
      </div>

      <AppDrawer
        open={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onExportPDF={handleExportPDF}
        onClear={() => setIsResetModalOpen(true)}
        onSupport={handleSupport}
        onGitHub={handleGitHub}
        isExporting={isExporting}
        isClearing={isLoading}
        disableExport={isExporting || isLoading || messages.length <= 1}
        disableClear={isLoading || messages.length <= 1}
      />

      <ConfirmationModal
        isOpen={isResetModalOpen}
        onClose={() => setIsResetModalOpen(false)}
        onConfirm={handleReset}
        title="Réinitialiser la conversation"
        message="Êtes-vous sûr de vouloir effacer toute l'historique de la conversation ? Cette action ne peut pas être annulée."
        confirmText="Réinitialiser"
        cancelText="Annuler"
      />

      <DisclaimerModal
        isOpen={isDisclaimerOpen}
        onClose={() => setIsDisclaimerOpen(false)}
      />
    </main>
  );
} 