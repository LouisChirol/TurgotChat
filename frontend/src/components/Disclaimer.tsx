'use client';

import { useDarkMode } from '@/hooks/useDarkMode';
import { Info, Moon, Sun } from 'lucide-react';

export function InfoButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="bg-yellow-400 hover:bg-yellow-500 dark:bg-yellow-500 dark:hover:bg-yellow-600 text-black p-2 rounded-full shadow-lg group relative"
      aria-label="Afficher le disclaimer"
      type="button"
    >
      <Info className="h-6 w-6" />
      <span className="absolute left-1/2 -translate-x-1/2 top-full mt-2 bg-gray-900 dark:bg-gray-700 text-white text-sm py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap max-w-[200px] text-center">
        Informations importantes
      </span>
    </button>
  );
}

export function DarkModeButton() {
  const { isDark, toggleDarkMode } = useDarkMode();
  return (
    <button
      onClick={toggleDarkMode}
      className="bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white p-2 rounded-full shadow-lg group relative"
      aria-label={isDark ? "Activer le mode clair" : "Activer le mode sombre"}
      type="button"
    >
      {isDark ? <Sun className="h-6 w-6" /> : <Moon className="h-6 w-6" />}
      <span className="absolute left-1/2 -translate-x-1/2 top-full mt-2 bg-gray-900 dark:bg-gray-700 text-white text-sm py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap max-w-[200px] text-center">
        {isDark ? "Mode clair" : "Mode sombre"}
      </span>
    </button>
  );
}

export function DisclaimerModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-lg max-w-2xl w-full p-6 max-h-[80vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-xl font-bold dark:text-white">⚠️ Informations importantes</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            type="button"
          >
            ✕
          </button>
        </div>
        <div className="prose prose-sm dark:prose-invert">
          <p className="mb-4">
            Ce site est un projet indépendant, non affilié à l&apos;État, au Gouvernement français, ni à aucune administration publique. Il ne constitue pas un service officiel.
          </p>
          <p className="mb-4">
            L&#39;intelligence artificielle utilisée ici est basée sur des modèles génératifs de langage, susceptibles de produire des informations inexactes, obsolètes ou erronées. Aucune garantie n&#39;est donnée quant à l&#39;exactitude, la fiabilité ou l&#39;exhaustivité des réponses fournies.
            L&#39;utilisateur reste seul responsable de l&#39;usage qu&#39;il fait des réponses générées.
          </p>
          <p className="mb-4">
            Il est fortement recommandé de vérifier systématiquement les informations obtenues via d&#39;autres sources fiables et officielles, en particulier pour toute décision personnelle, administrative, juridique ou médicale.
          </p>
          <p className="mb-4">
            Aucune donnée personnelle n&#39;est conservée, utilisée à des fins publicitaires ou transmise à des tiers. Les échanges sont temporaires et non stockés durablement.
          </p>
          <p className="mb-4">
            Ce projet est entièrement gratuit, non commercial, sans objectif lucratif.
          </p>
          <p>
            En utilisant ce site, vous acceptez ces conditions et reconnaissez que la responsabilité du fournisseur du service ne saurait être engagée en cas de mauvaise interprétation, d&#39;utilisation abusive ou de préjudice résultant des réponses de l&#39;IA.
          </p>
          <div className="mt-6 pt-4 border-t border-gray-200 text-center">
            <a
              href="https://buymeacoffee.com/louischirol"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <span>🙏</span>
              <span className="font-medium">Soutenir le projet</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

// The main Disclaimer component is now just a modal state manager (not used in layout)
export default function Disclaimer() {
  return null;
} 