'use client';

import AppDrawer from '@/components/AppDrawer';
import ChatInput from '@/components/ChatInput';
import ChatInterface from '@/components/ChatInterface';
import ConfirmationModal from '@/components/ConfirmationModal';
import { DarkModeButton, DisclaimerModal, InfoButton } from '@/components/Disclaimer';
import SupportButton from '@/components/SupportButton';
import { clearSession, sendMessage } from '@/services/api';
import { getSessionId } from '@/services/session';
import { Bars3Icon } from '@heroicons/react/24/outline';
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
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isDisclaimerOpen, setIsDisclaimerOpen] = useState(false);

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

  const handleSupport = () => {
    window.open('https://www.buymeacoffee.com/colbert', '_blank');
  };
  const handleGitHub = () => {
    window.open('https://github.com/louis030195/ColbertChat', '_blank');
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
            <div className="flex items-center gap-2">
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
        </div>
      </header>

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <ChatInterface messages={messages} isLoading={isLoading} />
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

      <DisclaimerModal isOpen={isDisclaimerOpen} onClose={() => setIsDisclaimerOpen(false)} />

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