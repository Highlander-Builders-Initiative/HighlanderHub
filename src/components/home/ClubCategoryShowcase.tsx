"use client";

import Link from "next/link";
import { FiArrowRight, FiCode, FiCompass, FiHeart, FiSmile, FiTrendingUp, FiFeather } from "react-icons/fi";

const CURATED_CATEGORIES = [
  {
    id: "academic",
    title: "Academic & Engineering",
    count: "150+ clubs",
    description: "ACM, IEEE, Pre-Med AMSA, SWE, and technical societies.",
    tags: ["ACM@UCR", "IEEE", "Pre-Health", "SWE"],
    icon: FiCode,
    href: "/events?cat=academic",
    badgeColor: "bg-blue-50 text-blue-700 border-blue-200/60",
  },
  {
    id: "arts",
    title: "Arts, Dance & Media",
    count: "45+ clubs",
    description: "Dance troupes, photography, theatre, and creative showcases.",
    tags: ["909 Dance", "AART Theatre", "Film Club", "Creative Guild"],
    icon: FiFeather,
    href: "/events?cat=arts",
    badgeColor: "bg-purple-50 text-purple-700 border-purple-200/60",
  },
  {
    id: "career",
    title: "Career & Professional",
    count: "60+ orgs",
    description: "Consulting, business fraternities, networking, and industry fairs.",
    tags: ["ALPFA", "Beta Alpha Psi", "Finance Club", "Consulting"],
    icon: FiTrendingUp,
    href: "/events?cat=career",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200/60",
  },
  {
    id: "cultural",
    title: "Cultural & Identity",
    count: "50+ orgs",
    description: "Affinity groups, cultural celebrations, and heritage unions.",
    tags: ["APSP Orgs", "Chicano Orgs", "Afrikan Union", "Heritage"],
    icon: FiHeart,
    href: "/events?cat=social",
    badgeColor: "bg-rose-50 text-rose-700 border-rose-200/60",
  },
  {
    id: "sports",
    title: "Recreation & Gaming",
    count: "70+ clubs",
    description: "Highlander Gaming, martial arts, archery, and outdoor trips.",
    tags: ["Highlander Gaming", "Archery", "Badminton", "Outdoors"],
    icon: FiSmile,
    href: "/events?cat=sports",
    badgeColor: "bg-amber-50 text-amber-700 border-amber-200/60",
  },
  {
    id: "community",
    title: "Service & Leadership",
    count: "55+ orgs",
    description: "Volunteer initiatives, student government, and campus service.",
    tags: ["ASUCR", "Best Buddies", "Circle K", "Food Pantry"],
    icon: FiCompass,
    href: "/events?cat=community",
    badgeColor: "bg-teal-50 text-teal-700 border-teal-200/60",
  },
];

export function ClubCategoryShowcase() {
  return (
    <section className="relative overflow-hidden py-14 md:py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        {/* Section Header */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-200/60 bg-blue-50/70 px-3 py-1 text-xs font-semibold text-blue-700">
              640+ STUDENT ORGANIZATIONS
            </div>
            <h2 className="mt-2 font-display text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl md:text-4xl">
              Clubs for whatever you&apos;re into
            </h2>
            <p className="mt-1 text-sm text-slate-600 sm:text-base">
              Discover communities, find meeting times, and connect with student leaders.
            </p>
          </div>

          <Link
            href="/events?cat=club"
            className="group inline-flex items-center gap-2 text-sm font-medium text-blue-600 transition-colors hover:text-blue-800"
          >
            <span>Explore all clubs</span>
            <FiArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Link>
        </div>

        {/* Scrollable Card Row */}
        <div className="mt-8 flex gap-4 overflow-x-auto pb-4 pt-1 scrollbar-none snap-x snap-mandatory sm:gap-6">
          {CURATED_CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            return (
              <Link
                key={cat.id}
                href={cat.href}
                className="group relative flex h-[230px] w-[270px] shrink-0 snap-start flex-col justify-between rounded-2xl border border-slate-200/90 bg-white p-5 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-blue-300 hover:shadow-md"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-xl border ${cat.badgeColor}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="text-xs font-medium text-slate-600">
                      {cat.count}
                    </span>
                  </div>

                  <h3 className="mt-3.5 font-display text-base font-bold text-slate-900 transition-colors group-hover:text-blue-600">
                    {cat.title}
                  </h3>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-600">
                    {cat.description}
                  </p>
                </div>

                <div className="flex flex-wrap gap-1.5 pt-2 border-t border-slate-100">
                  {cat.tags.slice(0, 3).map((t) => (
                    <span
                      key={t}
                      className="rounded-md bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-600 transition-colors group-hover:bg-blue-50 group-hover:text-blue-700"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
