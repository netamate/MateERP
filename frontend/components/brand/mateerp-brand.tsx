import Image from "next/image";
import type { ElementType } from "react";

type MateERPBrandProps = {
  className?: string;
  logoClassName?: string;
  wordmarkClassName?: string;
  heading?: boolean;
};

// Use the exact shared symbol from MateCRM; only the product wordmark differs.
export function MateERPLogoMark({ className = "" }: { className?: string }) {
  return (
    <Image
      alt=""
      aria-hidden="true"
      className={`object-contain ${className}`}
      height={494}
      priority
      src="/images/logo.png"
      width={521}
    />
  );
}

export function MateERPBrand({
  className = "",
  logoClassName = "",
  wordmarkClassName = "",
  heading = false,
}: MateERPBrandProps) {
  const Wordmark: ElementType = heading ? "h1" : "div";

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <MateERPLogoMark className={logoClassName} />
      <div className="min-w-0">
        <Wordmark className={`mateerp-wordmark leading-none ${wordmarkClassName}`}>
          MateERP
        </Wordmark>
      </div>
    </div>
  );
}
