import './globals.css';

export const metadata = {
  title: 'DeepSeek Skill Studio',
  description: 'Local Ollama DeepSeek skill runner for DOCX, PPTX, GitHub, and uploads'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
