import Link from "next/link";

const actions = [
  { href: "/new", title: "新しい作品を作る", body: "ジャンル選択からWorld Builderへ進む入口" },
  { href: "/projects", title: "作品を開く", body: "ローカルに保存した作品一覧を確認" },
  { href: "/settings", title: "設定", body: "保存・表示・将来のAI連携設定" },
];

export default function Home() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">M1 · APPLICATION FOUNDATION</p>
        <h1>Creative Consistency OS</h1>
        <p>物語世界を育て、設定を守り、長編を破綻させずに書き続けるための制作基盤。</p>
      </section>
      <section className="grid">
        {actions.map((action) => (
          <Link className="card" href={action.href} key={action.href}>
            <h2>{action.title}</h2>
            <p>{action.body}</p>
            <span>開く →</span>
          </Link>
        ))}
      </section>
    </main>
  );
}
