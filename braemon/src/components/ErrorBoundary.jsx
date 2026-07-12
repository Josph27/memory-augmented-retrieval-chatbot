import { Component } from "react";

export default class ErrorBoundary extends Component {
	constructor(props) {
		super(props);
		this.state = { hasError: false, error: null, errorInfo: null };
	}

	static getDerivedStateFromError(error) {
		return { hasError: true };
	}

	componentDidCatch(error, errorInfo) {
		this.setState({ error, errorInfo });
		console.error("ErrorBoundary caught an error:", error, errorInfo);
	}

	render() {
		if (this.state.hasError) {
			return (
				<div className="flex flex-col h-screen items-center justify-center bg-background p-margin">
					<div className="bg-surface-container-low border-2 border-error p-xl rounded-lg max-w-4xl w-full overflow-hidden shadow-lg">
						<h1 className="font-headline-md text-error mb-md flex items-center gap-sm">
							<span className="material-symbols-outlined text-[24px]">
								error
							</span>
							React Render Crash
						</h1>
						<p className="font-body-md text-on-surface-variant mb-lg">
							The application encountered an unhandled exception during
							rendering. The component tree was unmounted to prevent unstable
							state.
						</p>
						<div className="bg-surface-container-highest p-sm rounded overflow-auto max-h-[60vh] font-code text-[13px] text-on-surface">
							<p className="font-bold text-error mb-sm">
								{this.state.error && this.state.error.toString()}
							</p>
							<pre className="whitespace-pre-wrap">
								{this.state.errorInfo && this.state.errorInfo.componentStack}
							</pre>
						</div>
						<button
							className="mt-lg bg-surface-container-highest text-on-surface hover:bg-surface-dim px-md py-sm rounded font-label-md transition-colors"
							onClick={() => window.location.reload()}
						>
							Reload Application
						</button>
					</div>
				</div>
			);
		}

		return this.props.children;
	}
}
