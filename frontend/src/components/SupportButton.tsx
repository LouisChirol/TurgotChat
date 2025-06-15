const SupportButton = () => (
  <div className="fixed bottom-3 left-1/2 -translate-x-1/2 z-40">
    <a
      href="https://coff.ee/louischirol"
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm px-3 py-1.5 rounded-full shadow-md border border-gray-200 dark:border-gray-700"
      style={{ pointerEvents: 'auto' }}
    >
      <span className="text-[14px]">🙏</span>
      <span>Soutenir</span>
    </a>
  </div>
);

export default SupportButton; 