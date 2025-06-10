import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Disclaimer from '@/components/Disclaimer'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Colbert - Assistant Public Service',
  description: 'Votre assistant intelligent pour les services publics français',
  icons: {
    icon: '/colbert_avatar.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fr">
      <body className={`${inter.className} bg-gray-50`}>
        <Disclaimer />
        {children}
      </body>
    </html>
  )
} 