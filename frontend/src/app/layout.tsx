import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BEACON | Accessibility Intelligence",
  description:
    "Multi-page accessibility analysis platform with visual exploration, AI remediation, and benchmark-driven improvement.",
};

const extensionAttributeCleaner = `
  (function() {
    try {
      var origSetAttr = Element.prototype.setAttribute;
      Element.prototype.setAttribute = function(name, val) {
        if (name === 'bis_skin_checked' || name === 'bis_frame_id') return;
        return origSetAttr.apply(this, arguments);
      };
    } catch(e) {}
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(function(mutations) {
        for (var i = 0; i < mutations.length; i++) {
          var m = mutations[i];
          if (m.type === 'attributes' && (m.attributeName === 'bis_skin_checked' || m.attributeName === 'bis_frame_id')) {
            m.target.removeAttribute(m.attributeName);
          }
        }
      }).observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ['bis_skin_checked', 'bis_frame_id'] });
    }
  })();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <head>
        <script dangerouslySetInnerHTML={{ __html: extensionAttributeCleaner }} />
      </head>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
