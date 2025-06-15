'use client';

import ChatInput from '@/components/ChatInput';
import ChatInterface from '@/components/ChatInterface';
import ConfirmationModal from '@/components/ConfirmationModal';
import { clearSession, sendMessage } from '@/services/api';
import { getSessionId } from '@/services/session';
import Image from 'next/image';
import { useState } from 'react';

export default function Home() {
  const [messages, setMessages] = useState([
    {
      id: '1',
      content: 'Bonjour ! Je suis Colbert, posez moi toutes vos questions sur le service public et les démarches administratives. Comment puis-je vous aider?',
      isUser: false,
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);

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
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/export-pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ session_id: sessionId }),
      });

      if (!response.ok) {
        throw new Error('Failed to export PDF');
      }

      // Get the blob from the response
      const blob = await response.blob();
      
      // Create a download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `colbert_chat_${sessionId}.pdf`;
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
      await clearSession();
      setMessages([
        {
          id: '1',
          content: 'Bonjour ! Je suis Colbert, posez moi toutes vos questions sur le service public et les démarches administratives. Comment puis-je vous aider?',
          isUser: false,
        },
      ]);
      setIsResetModalOpen(false);
    } catch (error) {
      console.error('Error resetting session:', error);
      // You might want to show an error message to the user here
    }
  };

  return (
    <main className="flex flex-col h-[100dvh]">
      <header className="shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 transition-colors duration-200">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Image
                src="/colbert_v2.png"
                alt="Colbert Assistant"
                width={60}
                height={60}
                className="rounded-full"
              />
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold dark:text-white">Colbert</h1>
                  <div className="w-6 h-4 flex overflow-hidden rounded-sm shadow-sm">
                    <div className="flex-1 bg-blue-600"></div>
                    <div className="flex-1 bg-white"></div>
                    <div className="flex-1 bg-red-600"></div>
                  </div>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-300">Votre assistant administratif</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsResetModalOpen(true)}
                disabled={isLoading || messages.length <= 1}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isLoading || messages.length <= 1
                    ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                    : 'bg-red-50 dark:bg-red-900/50 text-red-600 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900'
                }`}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-4 w-4"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                    clipRule="evenodd"
                  />
                </svg>
                Vider la discussion
              </button>
              <button
                onClick={handleExportPDF}
                disabled={isExporting || isLoading || messages.length <= 1}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isExporting || isLoading || messages.length <= 1
                    ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                    : 'bg-blue-50 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900'
                }`}
              >
                {isExporting ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Export en cours...
                  </>
                ) : (
                  <>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-4 w-4"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                    >
                      <path
                        fillRule="evenodd"
                        d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Exporter en PDF
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <ChatInterface messages={messages} isLoading={isLoading} />
          </div>
        </div>

        <div className="shrink-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 pb-safe transition-colors duration-200">
          <div className="h-1 flex max-w-4xl mx-auto">
            <div className="flex-1 bg-blue-600"></div>
            <div className="flex-1 bg-white dark:bg-gray-800"></div>
            <div className="flex-1 bg-red-600"></div>
          </div>
          <div className="max-w-4xl mx-auto px-4 py-4">
            <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
          </div>
        </div>
      </div>

      <ConfirmationModal
        isOpen={isResetModalOpen}
        onClose={() => setIsResetModalOpen(false)}
        onConfirm={handleReset}
        title="Vider la discussion"
        message="Attention : cette action va réinitialiser la discussion et le contenu actuel sera définitivement perdu. Êtes-vous sûr de vouloir continuer ?"
        confirmText="Vider la discussion"
        cancelText="Annuler"
      />
    </main>
  );
} 