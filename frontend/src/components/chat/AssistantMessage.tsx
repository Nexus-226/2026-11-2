import ReactMarkdown from "react-markdown";

export default function AssistantMessage({ text }: { text: string }) {
  return (
    <div className="assistant-markdown">
      <ReactMarkdown
        skipHtml
        allowedElements={[
          "p",
          "br",
          "strong",
          "em",
          "ul",
          "ol",
          "li",
          "blockquote",
          "code",
          "pre",
          "a",
          "h1",
          "h2",
          "h3",
          "h4",
          "h5",
          "h6",
          "hr",
        ]}
        components={{
          a: ({ href, children }) => {
            // Only HTTP(S) destinations are navigable; no local or script URLs.
            if (!href || !/^https?:\/\//i.test(href))
              return <span>{children}</span>;
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
