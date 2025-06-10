'use client';

import ChatInput from '@/components/ChatInput';
import ChatInterface from '@/components/ChatInterface';
import { sendMessage } from '@/services/api';
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

  return (
    <main className="flex flex-col h-[100dvh]">
      <header className="shrink-0 bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4">
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
                <h1 className="text-2xl font-bold">Colbert</h1>
                <div className="w-6 h-4 flex overflow-hidden rounded-sm shadow-sm">
                  <div className="flex-1 bg-blue-600"></div>
                  <div className="flex-1 bg-white"></div>
                  <div className="flex-1 bg-red-600"></div>
                </div>
              </div>
              <p className="text-sm text-gray-600">Votre assistant administratif</p>
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

        <div className="shrink-0 bg-white border-t border-gray-200 pb-safe">
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
    </main>
  );
} 