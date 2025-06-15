'use client';

import { Coffee, Info } from 'lucide-react';
import { useState } from 'react';

export default function Disclaimer() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <div className="fixed top-4 right-12 flex gap-2 z-50">
        <button
          onClick={() => setIsOpen(true)}
          className="bg-yellow-400 hover:bg-yellow-500 text-black p-2 rounded-full shadow-lg group relative"
          aria-label="Afficher le disclaimer"
        >
          <Info className="h-6 w-6" />
          <span className="absolute left-1/2 -translate-x-1/2 top-full mt-2 bg-gray-900 text-white text-sm py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap max-w-[200px] text-center">
            Informations importantes
          </span>
        </button>
        <button
          onClick={() => window.open('https://coff.ee/louischirol', '_blank')}
          className="bg-orange-400 hover:bg-lime-500 text-black p-2 rounded-full shadow-lg group relative"
          aria-label="Soutenir le projet"
        >
          <Coffee className="h-6 w-6" />
          <span className="absolute left-1/2 -translate-x-1/2 top-full mt-2 bg-gray-900 text-white text-sm py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap max-w-[200px] text-center">
            Soutenir le projet
          </span>
        </button>
      </div>

      {isOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onClick={(e) => {
            // Only close if clicking the overlay itself, not its children
            if (e.target === e.currentTarget) {
              setIsOpen(false);
            }
          }}
        >
          <div className="bg-white rounded-lg max-w-2xl w-full p-6 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-xl font-bold">⚠️ Informations importantes</h2>
              <button
                onClick={() => setIsOpen(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            <div className="prose prose-sm">
              <p className="mb-4">
                Ce site est un projet indépendant, non affilié à l'État, au Gouvernement français, ni à aucune administration publique. Il ne constitue pas un service officiel.
              </p>
              <p className="mb-4">
                L'intelligence artificielle utilisée ici est basée sur des modèles génératifs de langage, susceptibles de produire des informations inexactes, obsolètes ou erronées. Aucune garantie n'est donnée quant à l'exactitude, la fiabilité ou l'exhaustivité des réponses fournies.
                L'utilisateur reste seul responsable de l'usage qu'il fait des réponses générées.
              </p>
              <p className="mb-4">
                Il est fortement recommandé de vérifier systématiquement les informations obtenues via d'autres sources fiables et officielles, en particulier pour toute décision personnelle, administrative, juridique ou médicale.
              </p>
              <p className="mb-4">
                Aucune donnée personnelle n'est conservée, utilisée à des fins publicitaires ou transmise à des tiers. Les échanges sont temporaires et non stockés durablement.
              </p>
              <p className="mb-4">
                Ce projet est entièrement gratuit, non commercial, sans objectif lucratif.
              </p>
              <p>
                En utilisant ce site, vous acceptez ces conditions et reconnaissez que la responsabilité du fournisseur du service ne saurait être engagée en cas de mauvaise interprétation, d'utilisation abusive ou de préjudice résultant des réponses de l'IA.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
} 