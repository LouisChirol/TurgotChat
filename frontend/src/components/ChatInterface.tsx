'use client';

import Message from '@/components/Message';
import Image from 'next/image';
import { useEffect, useRef } from 'react';

interface Message {
    id: string;
    content: string;
    isUser: boolean;
    sources?: Array<{
        url: string;
        title: string;
        excerpt: string;
    }>;
    secondarySources?: Array<{
        url: string;
        title: string;
        excerpt: string;
    }>;
    isError?: boolean;
}

interface ChatInterfaceProps {
    messages: Message[];
    isLoading: boolean;
}

const ChatInterface = ({ messages, isLoading }: ChatInterfaceProps) => {
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isLoading]);

    return (
        <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((message) => (
                    <Message
                        key={message.id}
                        role={message.isUser ? 'user' : 'assistant'}
                        content={message.content}
                        sources={message.sources}
                        secondarySources={message.secondarySources}
                        isError={message.isError}
                    />
                ))}
                {isLoading && (
                    <div className="flex justify-start gap-3">
                        <div className="w-12 h-12 rounded-full overflow-hidden flex-shrink-0">
                            <Image
                                src="/colbert_thinking.png"
                                alt="Colbert Thinking"
                                width={48}
                                height={48}
                                className="w-full h-full object-cover"
                            />
                        </div>
                        <div className="max-w-[80%] rounded-lg p-4 bg-gray-100 text-gray-800">
                            <div className="flex space-x-2">
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>
        </div>
    );
};

export default ChatInterface; 