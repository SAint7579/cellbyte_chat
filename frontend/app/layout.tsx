import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'CellByte Chat',
  description: 'AI-powered CSV data exploration',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}

