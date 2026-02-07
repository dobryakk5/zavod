'use client';

import { useState } from 'react';
import { kbDocumentsApi } from '@/lib/api/knowledgeBase';
import { generateHTML } from '@tiptap/html';
import TurndownService from 'turndown';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import { createKbExtensions } from '@/components/kb/tiptapExtensions';

interface ExportButtonProps {
  documentId: number;
  documentTitle: string;
}

const exportExtensions = createKbExtensions();

export default function ExportButton({ documentId, documentTitle }: ExportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const handleExportMarkdown = async () => {
    setIsExporting(true);
    try {
      const doc = await kbDocumentsApi.get(documentId);

      const html = generateHTML(doc.content ?? {}, exportExtensions);

      const turndownService = new TurndownService({
        headingStyle: 'atx',
        codeBlockStyle: 'fenced',
      });

      const markdown = turndownService.turndown(html);

      let output = '---\n';
      output += `title: "${doc.title}"\n`;
      output += `created: ${doc.created_at}\n`;
      output += `updated: ${doc.updated_at}\n`;
      output += '---\n\n';
      output += `# ${doc.title}\n\n`;
      output += markdown;

      const blob = new Blob([output], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = `${documentTitle.replace(/[^a-zа-я0-9]/gi, '-')}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export error:', error);
      alert('Ошибка экспорта в Markdown');
    } finally {
      setIsExporting(false);
      setShowMenu(false);
    }
  };

  const handleExportPDF = async () => {
    setIsExporting(true);
    try {
      const doc = await kbDocumentsApi.get(documentId);

      const html = generateHTML(doc.content ?? {}, exportExtensions);

      const container = window.document.createElement('div');
      container.innerHTML = `
        <div style="font-family: Arial; padding: 40px; max-width: 800px;">
          <h1>${doc.title}</h1>
          <p style="color: #666; margin-bottom: 30px;">
            ${new Date(doc.created_at).toLocaleDateString('ru-RU')}
          </p>
          ${html}
        </div>
      `;
      container.style.position = 'absolute';
      container.style.left = '-9999px';
      window.document.body.appendChild(container);

      await new Promise((resolve) => setTimeout(resolve, 500));

      const canvas = await html2canvas(container, {
        scale: 2,
        useCORS: true,
      });

      window.document.body.removeChild(container);

      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
      });

      const imgWidth = 210;
      const pageHeight = 297;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;
      let position = 0;

      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;

      while (heightLeft > 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }

      pdf.save(`${documentTitle.replace(/[^a-zа-я0-9]/gi, '-')}.pdf`);
    } catch (error) {
      console.error('PDF export error:', error);
      alert('Ошибка экспорта в PDF');
    } finally {
      setIsExporting(false);
      setShowMenu(false);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        disabled={isExporting}
        className="p-2 hover:bg-gray-100 rounded-lg disabled:opacity-50"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
      </button>

      {showMenu && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />

          <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-20">
            <button
              onClick={handleExportMarkdown}
              className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3"
            >
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
              <div>
                <div className="font-medium text-gray-900">Markdown</div>
                <div className="text-xs text-gray-500">.md файл</div>
              </div>
            </button>

            <button
              onClick={handleExportPDF}
              className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3"
            >
              <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
              <div>
                <div className="font-medium text-gray-900">PDF</div>
                <div className="text-xs text-gray-500">Документ PDF</div>
              </div>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
