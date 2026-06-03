import React, { useState, useEffect, useRef } from 'react';

export default function App() {
  const [directoryHandle, setDirectoryHandle] = useState(null);
  const [queue, setQueue] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedId, setSelectedId] = useState(null);

  const cancelRef = useRef(false);

  // Walk the directory recursively using the Directory Access API
  const scanDirectory = async (dirHandle) => {
    const list = [];
    const allowedExts = ['.pdf', '.docx', '.msg', '.eml'];
    
    async function walk(handle, currentPath = '') {
      for await (const entry of handle.values()) {
        if (entry.kind === 'file') {
          const file = await entry.getFile();
          if (allowedExts.some(ext => entry.name.toLowerCase().endsWith(ext))) {
            list.push({
              id: `${entry.name}-${file.size}-${file.lastModified}`,
              file,
              name: entry.name,
              relativePathDir: currentPath, // Store relative directories (e.g. 'subA/subB' or '')
              size: file.size,
              status: 'pending', // 'pending' | 'processing' | 'success' | 'error'
              markdown: '',
              savedPath: '',
              errorMsg: '',
            });
          }
        } else if (entry.kind === 'directory') {
          // Skip the output 'md' directory to avoid infinite loops or parsing outputs
          if (entry.name !== 'md') {
            await walk(entry, currentPath ? `${currentPath}/${entry.name}` : entry.name);
          }
        }
      }
    }
    
    await walk(dirHandle);
    return list;
  };

  // Open the native browser directory picker
  const selectFolder = async () => {
    try {
      const handle = await window.showDirectoryPicker();
      setDirectoryHandle(handle);
      
      const files = await scanDirectory(handle);
      setQueue(files);
      setCurrentIndex(0);
      setSelectedId(null);
    } catch (err) {
      console.error(err);
      if (err.name !== 'AbortError') {
        alert('Failed to access folder: ' + err.message);
      }
    }
  };

  // Helper to resolve nested directories handles inside 'md'
  const resolveTargetDirHandle = async (rootMdHandle, relativePathDir) => {
    let currentDirHandle = rootMdHandle;
    if (relativePathDir) {
      const parts = relativePathDir.split('/');
      for (const part of parts) {
        currentDirHandle = await currentDirHandle.getDirectoryHandle(part, { create: true });
      }
    }
    return currentDirHandle;
  };

  // Convert queue file-by-file
  const startConversion = async () => {
    if (queue.length === 0 || !directoryHandle) return;
    
    setIsProcessing(true);
    cancelRef.current = false;
    setCurrentIndex(0);

    const updatedQueue = [...queue];

    try {
      // Create or retrieve the 'md' folder inside the selected folder
      const mdDirHandle = await directoryHandle.getDirectoryHandle('md', { create: true });

      for (let i = 0; i < updatedQueue.length; i++) {
        if (cancelRef.current) {
          break;
        }

        // Only convert if it's currently pending or processing (skip already completed files)
        if (updatedQueue[i].status === 'success') {
          setCurrentIndex(i + 1);
          continue;
        }

        updatedQueue[i].status = 'processing';
        setQueue([...updatedQueue]);

        try {
          const formData = new FormData();
          formData.append('file', updatedQueue[i].file);

          const response = await fetch('http://localhost:8000/convert', {
            method: 'POST',
            body: formData,
          });

          if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Server error (${response.status})`);
          }

          const data = await response.json();
          const markdownContent = data.markdown;
          
          // Replicate nested subfolders inside 'md'
          const targetDirHandle = await resolveTargetDirHandle(mdDirHandle, updatedQueue[i].relativePathDir);

          // Collision prevention logic inside the specific target subdirectory
          const lastDotIndex = updatedQueue[i].name.lastIndexOf('.');
          const baseName = lastDotIndex !== -1 ? updatedQueue[i].name.substring(0, lastDotIndex) : updatedQueue[i].name;
          
          let targetFilename = `${baseName}.md`;
          let exists = true;
          let counter = 1;
          
          while (exists) {
            try {
              await targetDirHandle.getFileHandle(targetFilename, { create: false });
              // If no error, the file exists! Try a new name
              targetFilename = `${baseName}_${counter}.md`;
              counter++;
            } catch (err) {
              // File does not exist, we are good to go!
              exists = false;
            }
          }

          // Create the file and write to local disk
          const fileHandle = await targetDirHandle.getFileHandle(targetFilename, { create: true });
          const writable = await fileHandle.createWritable();
          await writable.write(markdownContent);
          await writable.close();
          
          updatedQueue[i].status = 'success';
          updatedQueue[i].markdown = markdownContent;
          const relativeSubpath = updatedQueue[i].relativePathDir ? `${updatedQueue[i].relativePathDir}/` : '';
          updatedQueue[i].savedPath = `${directoryHandle.name}/md/${relativeSubpath}${targetFilename}`;
        } catch (err) {
          updatedQueue[i].status = 'error';
          updatedQueue[i].errorMsg = err.message || 'Unknown conversion error';
        }

        setCurrentIndex(i + 1);
        setQueue([...updatedQueue]);
      }
    } catch (e) {
      alert('Failed to write files to the target folder: ' + e.message);
    }

    setIsProcessing(false);
  };

  // Retry converting a single failed item
  const retryFile = async (id) => {
    const itemIndex = queue.findIndex(item => item.id === id);
    if (itemIndex === -1 || !directoryHandle) return;

    const updatedQueue = [...queue];
    updatedQueue[itemIndex].status = 'processing';
    updatedQueue[itemIndex].errorMsg = '';
    setQueue([...updatedQueue]);

    try {
      const mdDirHandle = await directoryHandle.getDirectoryHandle('md', { create: true });
      
      const formData = new FormData();
      formData.append('file', updatedQueue[itemIndex].file);

      const response = await fetch('http://localhost:8000/convert', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error (${response.status})`);
      }

      const data = await response.json();
      const markdownContent = data.markdown;
      
      // Replicate nested subfolders inside 'md'
      const targetDirHandle = await resolveTargetDirHandle(mdDirHandle, updatedQueue[itemIndex].relativePathDir);

      // Collision prevention logic
      const lastDotIndex = updatedQueue[itemIndex].name.lastIndexOf('.');
      const baseName = lastDotIndex !== -1 ? updatedQueue[itemIndex].name.substring(0, lastDotIndex) : updatedQueue[itemIndex].name;
      
      let targetFilename = `${baseName}.md`;
      let exists = true;
      let counter = 1;
      
      while (exists) {
        try {
          await targetDirHandle.getFileHandle(targetFilename, { create: false });
          targetFilename = `${baseName}_${counter}.md`;
          counter++;
        } catch (err) {
          exists = false;
        }
      }

      const fileHandle = await targetDirHandle.getFileHandle(targetFilename, { create: true });
      const writable = await fileHandle.createWritable();
      await writable.write(markdownContent);
      await writable.close();

      updatedQueue[itemIndex].status = 'success';
      updatedQueue[itemIndex].markdown = markdownContent;
      const relativeSubpath = updatedQueue[itemIndex].relativePathDir ? `${updatedQueue[itemIndex].relativePathDir}/` : '';
      updatedQueue[itemIndex].savedPath = `${directoryHandle.name}/md/${relativeSubpath}${targetFilename}`;
    } catch (err) {
      updatedQueue[itemIndex].status = 'error';
      updatedQueue[itemIndex].errorMsg = err.message || 'Unknown conversion error';
    }

    setQueue([...updatedQueue]);
  };

  const stopConversion = () => {
    cancelRef.current = true;
    setIsProcessing(false);
  };

  const clearQueue = () => {
    setQueue([]);
    setDirectoryHandle(null);
    setCurrentIndex(0);
    setSelectedId(null);
  };

  const selectedItem = queue.find(item => item.id === selectedId);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    alert('Markdown copied to clipboard!');
  };

  const formatSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-900 bg-slate-900/20 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-extrabold bg-gradient-to-r from-violet-400 via-indigo-200 to-cyan-400 bg-clip-text text-transparent">
                MarkItDown Folder Converter
              </h1>
              <p className="text-xs text-slate-500 font-medium">Local Batch Markdown Conversion Utility</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-slate-400 font-medium">Connected to Localhost</span>
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column - Controls and Queue (7 cols) */}
        <section className="lg:col-span-7 flex flex-col gap-6">
          
          {/* Card 1: Directory Selection */}
          <div className="bg-slate-900/40 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-6 shadow-xl flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <span className="h-6 w-6 rounded-full bg-violet-950 border border-violet-500/30 flex items-center justify-center text-xs font-bold text-violet-400">1</span>
              <h2 className="text-lg font-bold text-slate-200">Select Local Folder</h2>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Click below to select your folder. The application will scan the folder recursively, convert documents, and replicate the nested subfolder directory structure inside the automatically created <strong>`md/`</strong> folder.
            </p>
            
            {directoryHandle ? (
              <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-violet-950/40 border border-violet-900/50 text-violet-400">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Active Folder</p>
                    <p className="text-sm font-semibold text-slate-200">{directoryHandle.name}</p>
                  </div>
                </div>
                <button
                  onClick={clearQueue}
                  disabled={isProcessing}
                  className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs font-bold rounded-lg border border-slate-800 transition"
                >
                  Change Folder
                </button>
              </div>
            ) : (
              <button
                onClick={selectFolder}
                disabled={isProcessing}
                className="w-full relative border-2 border-dashed border-slate-800 hover:border-violet-500/60 rounded-xl p-8 flex flex-col items-center justify-center bg-slate-950/20 hover:bg-slate-900/20 group transition cursor-pointer"
              >
                <div className="flex flex-col items-center gap-3">
                  <div className="p-3 rounded-full bg-slate-900 border border-slate-800 group-hover:border-violet-500/30 transition text-slate-400 group-hover:text-violet-400">
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-semibold text-slate-300">Click to Select Folder</p>
                    <p className="text-xs text-slate-500 mt-1">Converts PDF, DOCX, MSG, and EML documents</p>
                  </div>
                </div>
              </button>
            )}
          </div>

          {/* Card 2: Queue & Conversion Progress */}
          {queue.length > 0 && (
            <div className="bg-slate-900/40 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-6 shadow-xl flex flex-col gap-6 flex-1 min-h-[300px]">
              
              {/* Progress Summary */}
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-slate-200">Conversion Queue</h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {currentIndex} of {queue.length} files processed
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {isProcessing ? (
                      <button
                        onClick={stopConversion}
                        className="px-4 py-2 bg-rose-950 hover:bg-rose-900 border border-rose-800/50 text-rose-200 rounded-lg text-xs font-bold transition"
                      >
                        Stop
                      </button>
                    ) : (
                      <button
                        onClick={startConversion}
                        disabled={queue.length === 0}
                        className="px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-40 disabled:pointer-events-none text-white rounded-lg text-xs font-bold shadow-lg shadow-indigo-500/10 transition"
                      >
                        Start Batch
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-slate-950 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-violet-500 to-indigo-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${(currentIndex / queue.length) * 100}%` }}
                  />
                </div>
              </div>

              {/* Queue List Viewport */}
              <div className="flex-1 overflow-y-auto max-h-[350px] border border-slate-850 bg-slate-950/20 rounded-xl divide-y divide-slate-900">
                {queue.map((item) => {
                  const isSelected = item.id === selectedId;
                  return (
                    <div
                      key={item.id}
                      onClick={() => setSelectedId(item.id)}
                      className={`flex items-center justify-between p-3.5 cursor-pointer text-sm transition ${
                        isSelected ? 'bg-slate-900/60' : 'hover:bg-slate-900/20'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0 pr-4">
                        <div className="shrink-0 text-slate-400">
                          {item.name.toLowerCase().endsWith('.pdf') && (
                            <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                            </svg>
                          )}
                          {item.name.toLowerCase().endsWith('.docx') && (
                            <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                          )}
                          {(item.name.toLowerCase().endsWith('.msg') || item.name.toLowerCase().endsWith('.eml')) && (
                            <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                            </svg>
                          )}
                        </div>
                        <div className="min-w-0 flex flex-col gap-0.5">
                          <span className="font-semibold text-slate-200 truncate">{item.name}</span>
                          <span className="text-xs text-slate-500 font-mono">
                            {item.relativePathDir ? `${item.relativePathDir}/` : ''}{formatSize(item.size)}
                          </span>
                        </div>
                      </div>

                      <div className="shrink-0 flex items-center">
                        {item.status === 'pending' && (
                          <span className="text-xs text-slate-500 font-bold px-2 py-0.5 bg-slate-900 border border-slate-800 rounded-full">Pending</span>
                        )}
                        {item.status === 'processing' && (
                          <div className="flex items-center gap-1.5 text-xs text-violet-400 font-bold px-2.5 py-0.5 bg-violet-950/20 border border-violet-900/50 rounded-full">
                            <svg className="animate-spin h-3.5 w-3.5 text-violet-400" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                            <span>Parsing</span>
                          </div>
                        )}
                        {item.status === 'success' && (
                          <span className="text-xs text-emerald-400 font-bold px-2 py-0.5 bg-emerald-950/20 border border-emerald-900/30 rounded-full flex items-center gap-1">
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                            Done
                          </span>
                        )}
                        {item.status === 'error' && (
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs text-rose-400 font-bold px-2 py-0.5 bg-rose-950/20 border border-rose-900/30 rounded-full flex items-center gap-1">
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                              </svg>
                              Error
                            </span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                retryFile(item.id);
                              }}
                              className="p-1 hover:bg-slate-800 text-slate-400 hover:text-violet-400 rounded-lg transition"
                              title="Retry conversion"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3m0 0l3 3" />
                              </svg>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </section>

        {/* Right Column - Preview Panel (5 cols) */}
        <section className="lg:col-span-5 flex flex-col">
          <div className="bg-slate-900/40 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-6 shadow-xl flex flex-col flex-1 min-h-[500px] lg:max-h-[calc(100vh-120px)] overflow-hidden">
            <h2 className="text-lg font-bold text-slate-200 mb-4 pb-3 border-b border-slate-800/50 flex items-center justify-between shrink-0">
              <span>Output Preview</span>
              {selectedItem?.status === 'success' && (
                <button
                  onClick={() => copyToClipboard(selectedItem.markdown)}
                  className="px-3 py-1 bg-slate-800 hover:bg-slate-700 active:bg-slate-750 text-slate-300 text-xs font-bold rounded-lg border border-slate-750 transition"
                >
                  Copy Markdown
                </button>
              )}
            </h2>

            {selectedItem ? (
              <div className="flex-1 flex flex-col min-h-0">
                <div className="mb-4 shrink-0">
                  <div className="text-sm font-bold text-slate-200 truncate">{selectedItem.name}</div>
                  {selectedItem.savedPath && (
                    <div className="text-xs text-slate-400 mt-1 font-mono break-all flex items-center gap-1">
                      <svg className="w-3.5 h-3.5 text-violet-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8 4H6a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-2m-4-1v8m0 0l3-3m-3 3L9 8m-5 5h2.586a1 1 0 01.707.293l2.414 2.414a1 1 0 00.707.293H19" />
                      </svg>
                      <span>Saved to: {selectedItem.savedPath}</span>
                    </div>
                  )}
                </div>

                <div className="flex-1 overflow-y-auto bg-slate-950/70 border border-slate-850/80 rounded-xl p-4 min-h-0 font-mono text-xs">
                  {selectedItem.status === 'success' ? (
                    selectedItem.markdown.trim() ? (
                      <pre className="whitespace-pre-wrap text-slate-300 select-text leading-relaxed">
                        {selectedItem.markdown}
                      </pre>
                    ) : (
                      <span className="text-slate-500 italic">Document was empty or converted to empty Markdown.</span>
                    )
                  ) : selectedItem.status === 'error' ? (
                    <div className="flex flex-col gap-4 text-rose-400">
                      <div className="flex flex-col gap-2">
                        <span className="font-bold text-sm">Failed Conversion Detail</span>
                        <p className="leading-relaxed bg-rose-950/10 border border-rose-900/30 rounded-lg p-3.5 text-rose-300 font-sans text-xs">
                          {selectedItem.errorMsg}
                        </p>
                      </div>
                      <button
                        onClick={() => retryFile(selectedItem.id)}
                        className="self-start px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white rounded-lg text-xs font-bold transition shadow-lg shadow-indigo-500/10"
                      >
                        Retry Conversion
                      </button>
                    </div>
                  ) : selectedItem.status === 'processing' ? (
                    <div className="h-full flex flex-col items-center justify-center gap-3 text-slate-400 py-12">
                      <svg className="animate-spin h-6 w-6 text-violet-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span className="text-xs font-semibold">Converting file in backend...</span>
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center text-slate-500 italic py-12">
                      Waiting to start conversion...
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-12 border border-dashed border-slate-800 rounded-xl">
                <svg className="w-10 h-10 text-slate-700 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-xs font-medium text-slate-400">No Document Selected</p>
                <p className="text-[10px] text-slate-600 mt-1 max-w-[200px] text-center">
                  Select a completed file from the queue list to preview its converted Markdown output.
                </p>
              </div>
            )}
          </div>
        </section>

      </main>
    </div>
  );
}
