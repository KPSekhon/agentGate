interface StatCardProps {
  title: string;
  value: number | string;
  color?: "blue" | "red" | "green" | "amber";
}

const colorMap = {
  blue: "border-blue-500/30 text-blue-400",
  red: "border-red-500/30 text-red-400",
  green: "border-green-500/30 text-green-400",
  amber: "border-amber-500/30 text-amber-400",
};

export default function StatCard({ title, value, color = "blue" }: StatCardProps) {
  return (
    <div
      className={`bg-gray-900 border ${colorMap[color]} rounded-lg p-5`}
    >
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
        {title}
      </p>
      <p className="text-3xl font-bold">{value}</p>
    </div>
  );
}
