import { Outlet, NavLink } from "react-router-dom";

const CubeLogo = () => (
	<svg
		width="32"
		height="32"
		viewBox="0 0 32 32"
		fill="none"
		xmlns="http://www.w3.org/2000/svg"
		className="group-hover:rotate-90 transition-transform duration-500 ease-in-out"
	>
		<path d="M16 2L4 8V24L16 30L28 24V8L16 2Z" fill="#6b5b95" />
		<path d="M16 2L28 8L16 14L4 8L16 2Z" fill="#8e7cc3" />
		<path d="M16 14V30L28 24V8L16 14Z" fill="#4b3f6b" />
		<path d="M4 8V24L16 30V14L4 8Z" fill="#5a4d82" />
	</svg>
);

function Layout() {
	const links = [
		{ to: "/chats", label: "Chats" },
		{ to: "/documents", label: "Documents" },
		{ to: "/memories", label: "Memories" },
	];

	return (
		<div className="min-h-screen bg-gradient-animate overflow-x-hidden flex flex-col">
			{/* Fixed Top Nav */}
			<nav className="fixed top-0 w-full z-50 h-12 border-b border-outline-variant/20 bg-surface flex items-center px-margin gap-xl">
				<NavLink to="/" className="group cursor-pointer">
					<CubeLogo />
				</NavLink>
				<div className="flex items-center gap-xs md:gap-lg h-full">
					{links.map(({ to, label }) => (
						<NavLink
							key={to}
							to={to}
							className={({ isActive }) =>
								isActive
									? "text-primary font-bold border-b-2 border-primary h-full flex items-center pb-0 cursor-pointer active:opacity-80"
									: "text-on-surface-variant font-medium hover:text-on-surface transition-colors hover:bg-surface-container-high h-full flex items-center px-sm rounded-sm cursor-pointer active:opacity-80"
							}
						>
							{label}
						</NavLink>
					))}
				</div>
				<div className="ml-auto" />
			</nav>

			{/* Main Content */}
			<main className="flex-1 mt-12 w-full">
				<Outlet />
			</main>
		</div>
	);
}

export default Layout;
