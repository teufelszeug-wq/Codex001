import Link from "next/link";

const actions = [
  { href: "/new", title: "新しい作品を作る", body: "ジャンル選択 → 制作モード → World DNAの順で開始" },
  { href: "/projects", title: "作品を開く", body: "ローカルに保存した作品とWorld Builder設定を確認" },
  { href: "/settings", title: "設定", body: "保存・表示・将来のAI連携設定" },
];

export default function Home() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">M2 · WORLD BUILDER ALPHA</p>
        <h1>Creative Consistency OS</h1>
        <p>ジャンルを入口に、作者が自分の方法で世界を組み立てる。プリセットは提案であり、選択権は常に作者にあります。</p>
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