import ReactMarkdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import rehypeSlug from 'rehype-slug';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';

import CustomCodeBlock from '@/pages/features/custommdxcomponent/CustomCodeBlock';
import CustomHeading from '@/pages/features/custommdxcomponent/CustomHeading';

import './markdown.css';
import 'katex/dist/katex.min.css';

/**
 * Render published documentation as sanitized Markdown.
 *
 * Commit previously compiled stored MDX into executable JavaScript in every
 * reader's browser. Public documentation must remain content, not code, so
 * arbitrary JSX/import/export expressions are intentionally unsupported.
 */
const MarkdownRenderer = ({ mdxContent }: { mdxContent: string }) => (
    <div className="markdown-body">
        <ReactMarkdown
            remarkPlugins={[remarkMath, remarkBreaks, remarkGfm]}
            rehypePlugins={[
                rehypeRaw,
                rehypeSlug,
                rehypeKatex,
                rehypeSanitize,
            ]}
            components={{
                pre: ({ children, ...props }) => <CustomCodeBlock {...props}>{children}</CustomCodeBlock>,
                h2: ({ id, children }) => <CustomHeading id={id || ''} as="h2">{children}</CustomHeading>,
                h3: ({ id, children }) => <CustomHeading id={id || ''} as="h3">{children}</CustomHeading>,
                h4: ({ id, children }) => <CustomHeading id={id || ''} as="h4">{children}</CustomHeading>,
                h5: ({ id, children }) => <CustomHeading id={id || ''} as="h5">{children}</CustomHeading>,
                h6: ({ id, children }) => <CustomHeading id={id || ''} as="h6">{children}</CustomHeading>,
            }}
        >
            {mdxContent}
        </ReactMarkdown>
    </div>
);

export default MarkdownRenderer;
