import { Card, CardContent } from '@/components/ui/card'
import { ScanSearch, Eye, Sparkles } from 'lucide-react'

export function Features() {
    return (
        <section className="border-b-2 border-black bg-white px-4 py-32 lg:py-40 md:px-10">
            <div className="mx-auto max-w-7xl">
                <div className="relative">
                    <div className="relative z-10 grid grid-cols-6 gap-4">
                        <Card className="relative col-span-full flex overflow-hidden lg:col-span-2 border-2 border-black rounded-2xl bg-[#ffe17c]" style={{ boxShadow: '4px 4px 0px 0px #000' }}>
                            <CardContent className="relative m-auto size-fit pt-6">
                                <div className="relative flex h-24 w-56 items-center">
                                    <svg className="text-black/10 absolute inset-0 size-full" viewBox="0 0 254 104" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <path
                                            d="M112.891 97.7022C140.366 97.0802 171.004 94.6715 201.087 87.5116C210.43 85.2881 219.615 82.6412 228.284 78.2473C232.198 76.3179 235.905 73.9942 239.348 71.3124C241.85 69.2557 243.954 66.7571 245.555 63.9408C249.34 57.3235 248.281 50.5341 242.498 45.6109C239.033 42.7237 235.228 40.2703 231.169 38.3054C219.443 32.7209 207.141 28.4382 194.482 25.534C184.013 23.1927 173.358 21.7755 162.64 21.2989C161.376 21.3512 160.113 21.181 158.908 20.796C158.034 20.399 156.857 19.1682 156.962 18.4535C157.115 17.8927 157.381 17.3689 157.743 16.9139C158.104 16.4588 158.555 16.0821 159.067 15.8066C160.14 15.4683 161.274 15.3733 162.389 15.5286C179.805 15.3566 196.626 18.8373 212.998 24.462C220.978 27.2494 228.798 30.4747 236.423 34.1232C240.476 36.1159 244.202 38.7131 247.474 41.8258C254.342 48.2578 255.745 56.9397 251.841 65.4892C249.793 69.8582 246.736 73.6777 242.921 76.6327C236.224 82.0192 228.522 85.4602 220.502 88.2924C205.017 93.7847 188.964 96.9081 172.738 99.2109C153.442 101.949 133.993 103.478 114.506 103.79C91.1468 104.161 67.9334 102.97 45.1169 97.5831C36.0094 95.5616 27.2626 92.1655 19.1771 87.5116C13.839 84.5746 9.1557 80.5802 5.41318 75.7725C-0.54238 67.7259 -1.13794 59.1763 3.25594 50.2827C5.82447 45.3918 9.29572 41.0315 13.4863 37.4319C24.2989 27.5721 37.0438 20.9681 50.5431 15.7272C68.1451 8.8849 86.4883 5.1395 105.175 2.83669C129.045 0.0992292 153.151 0.134761 177.013 2.94256C197.672 5.23215 218.04 9.01724 237.588 16.3889C240.089 17.3418 242.498 18.5197 244.933 19.6446C246.627 20.4387 247.725 21.6695 246.997 23.615C246.455 25.1105 244.814 25.5605 242.63 24.5811C230.322 18.9961 217.233 16.1904 204.117 13.4376C188.761 10.3438 173.2 8.36665 157.558 7.52174C129.914 5.70776 102.154 8.06792 75.2124 14.5228C60.6177 17.8788 46.5758 23.2977 33.5102 30.6161C26.6595 34.3329 20.4123 39.0673 14.9818 44.658C12.9433 46.8071 11.1336 49.1622 9.58207 51.6855C4.87056 59.5336 5.61172 67.2494 11.9246 73.7608C15.2064 77.0494 18.8775 79.925 22.8564 82.3236C31.6176 87.7101 41.3848 90.5291 51.3902 92.5804C70.6068 96.5773 90.0219 97.7419 112.891 97.7022Z"
                                            fill="currentColor"
                                        />
                                    </svg>
                                    <span className="mx-auto block w-fit text-5xl font-extrabold font-cabinet">WCAG</span>
                                </div>
                                <h2 className="mt-6 text-center text-3xl font-extrabold font-cabinet">2.2 Compliant</h2>
                            </CardContent>
                        </Card>
                        <Card className="relative col-span-full overflow-hidden sm:col-span-3 lg:col-span-2 border-2 border-black rounded-2xl bg-white" style={{ boxShadow: '4px 4px 0px 0px #000' }}>
                            <CardContent className="pt-6">
                                <div className="relative mx-auto flex aspect-square size-32 rounded-full border-2 border-black before:absolute before:-inset-2 before:rounded-full before:border-2 before:border-black/20">
                                    <ScanSearch className="m-auto h-fit w-16 text-[#171e19]" strokeWidth={1.5} />
                                </div>
                                <div className="relative z-10 mt-6 space-y-2 text-center">
                                    <h2 className="text-lg font-extrabold font-cabinet transition">Native Topology Crawling</h2>
                                    <p className="text-sm font-medium text-zinc-600">Crawl entire domains with structural DOM skeleton clustering, cutting redundant loops by 66.7%.</p>
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="relative col-span-full overflow-hidden sm:col-span-3 lg:col-span-2 border-2 border-black rounded-2xl bg-[#b7c6c2]" style={{ boxShadow: '4px 4px 0px 0px #000' }}>
                            <CardContent className="pt-6">
                                <div className="pt-6 lg:px-6">
                                    <svg className="w-full text-[#171e19]" viewBox="0 0 386 123" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <rect width="386" height="123" rx="10" />
                                        <g clipPath="url(#clip0_0_106)">
                                            <circle className="text-[#171e19]/30" cx="29" cy="29" r="15" fill="currentColor" />
                                            <path d="M29 23V35" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                            <path d="M35 29L29 35L23 29" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                            <path
                                                d="M55.2373 32H58.7988C61.7383 32 63.4404 30.1816 63.4404 27.0508V27.0371C63.4404 23.9404 61.7246 22.1357 58.7988 22.1357H55.2373V32ZM56.7686 30.6807V23.4551H58.6279C60.6719 23.4551 61.8818 24.7881 61.8818 27.0576V27.0713C61.8818 29.3613 60.6924 30.6807 58.6279 30.6807H56.7686ZM69.4922 32.1436C71.666 32.1436 72.999 30.6875 72.999 28.2949V28.2812C72.999 25.8887 71.6592 24.4326 69.4922 24.4326C67.3184 24.4326 65.9785 25.8955 65.9785 28.2812V28.2949C65.9785 30.6875 67.3115 32.1436 69.4922 32.1436ZM69.4922 30.9062C68.2139 30.9062 67.4961 29.9424 67.4961 28.2949V28.2812C67.4961 26.6338 68.2139 25.6699 69.4922 25.6699C70.7637 25.6699 71.4883 26.6338 71.4883 28.2812V28.2949C71.4883 29.9355 70.7637 30.9062 69.4922 30.9062Z"
                                                fill="currentColor"
                                            />
                                        </g>
                                        <path
                                            fillRule="evenodd"
                                            clipRule="evenodd"
                                            d="M0.148438 231V179.394L1.92188 180.322L2.94482 177.73L4.05663 183.933L6.77197 178.991L7.42505 184.284L9.42944 187.985L11.1128 191.306V155.455L13.6438 153.03V145.122L14.2197 142.829V150.454V154.842L15.5923 160.829L17.0793 172.215H19.2031V158.182L20.7441 153.03L22.426 148.111V142.407L24.7471 146.86V128.414L26.7725 129.918V120.916L28.1492 118.521L28.4653 127.438L29.1801 123.822L31.0426 120.525V130.26L32.3559 134.71L34.406 145.122V137.548L35.8982 130.26L37.1871 126.049L38.6578 134.71L40.659 138.977V130.26V126.049L43.7557 130.26V123.822L45.972 112.407L47.3391 103.407V92.4726L49.2133 98.4651V106.053L52.5797 89.7556L54.4559 82.7747L56.1181 87.9656L58.9383 89.7556V98.4651L60.7617 103.407L62.0545 123.822L63.8789 118.066L65.631 122.082L68.5479 114.229L70.299 109.729L71.8899 118.066L73.5785 123.822V130.26L74.9446 134.861L76.9243 127.87L78.352 134.71V138.977L80.0787 142.407V152.613L83.0415 142.407V130.26L86.791 123.822L89.0121 116.645V122.082L90.6059 127.87L92.3541 131.77L93.7104 123.822L95.4635 118.066L96.7553 122.082V137.548"
                                            fill="url(#paint0_linear_0_106)"
                                        />
                                        <path
                                            className="text-[#171e19]"
                                            d="M3 121.077C3 121.077 15.3041 93.6691 36.0195 87.756C56.7349 81.8429 66.6632 80.9723 66.6632 80.9723C66.6632 80.9723 80.0327 80.9723 91.4656 80.9723C102.898 80.9723 100.415 64.2824 108.556 64.2824C116.696 64.2824 117.693 92.1332 125.226 92.1332C132.759 92.1332 142.07 78.5115 153.591 80.9723C165.113 83.433 186.092 92.1332 193 92.1332C199.908 92.1332 205.274 64.2824 213.017 64.2824C220.76 64.2824 237.832 93.8946 243.39 92.1332C248.948 90.3718 257.923 60.5 265.284 60.5C271.145 60.5 283.204 87.7182 285.772 87.756"
                                            stroke="currentColor"
                                            strokeWidth="3"
                                        />
                                        <defs>
                                            <linearGradient id="paint0_linear_0_106" x1="3" y1="60" x2="3" y2="123" gradientUnits="userSpaceOnUse">
                                                <stop className="text-[#171e19]/15" stopColor="currentColor" />
                                                <stop className="text-transparent" offset="1" stopColor="currentColor" stopOpacity="0.103775" />
                                            </linearGradient>
                                            <clipPath id="clip0_0_106">
                                                <rect width="358" height="30" fill="white" transform="translate(14 14)" />
                                            </clipPath>
                                        </defs>
                                    </svg>
                                </div>
                                <div className="relative z-10 mt-10 space-y-2 text-center">
                                    <h2 className="text-lg font-extrabold font-cabinet transition">Real-Time Tracking</h2>
                                    <p className="text-sm font-medium text-zinc-700">Monitor your accessibility score improvements across multiple historical scans.</p>
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="relative col-span-full overflow-hidden lg:col-span-3 border-2 border-black rounded-2xl bg-[#171e19] text-white" style={{ boxShadow: '4px 4px 0px 0px #000' }}>
                            <CardContent className="grid pt-6 sm:grid-cols-2">
                                <div className="relative z-10 flex flex-col justify-between space-y-12 lg:space-y-6">
                                    <div className="relative flex aspect-square size-12 rounded-full border-2 border-[#ffe17c]/40 before:absolute before:-inset-2 before:rounded-full before:border before:border-[#ffe17c]/20">
                                        <Sparkles className="m-auto size-5 text-[#ffe17c]" strokeWidth={1.5} />
                                    </div>
                                    <div className="space-y-2">
                                        <h2 className="text-lg font-extrabold font-cabinet text-white transition">NVIDIA NIM AI Sandbox</h2>
                                        <p className="text-sm font-medium text-zinc-400">Context-aware AI fixes verified in a headless DOM container with a strict zero-regression guarantee.</p>
                                    </div>
                                </div>
                                <div className="rounded-tl-2xl relative -mb-6 -mr-6 mt-6 h-fit border-l-2 border-t-2 border-zinc-700 p-6 py-6 sm:ml-6">
                                    <div className="absolute left-3 top-2 flex gap-1">
                                        <span className="block size-2 rounded-full border border-zinc-600 bg-zinc-700"></span>
                                        <span className="block size-2 rounded-full border border-zinc-600 bg-zinc-700"></span>
                                        <span className="block size-2 rounded-full border border-zinc-600 bg-zinc-700"></span>
                                    </div>
                                    <div className="mt-4 space-y-2 font-mono text-xs text-zinc-400">
                                        <p className="text-[#ffe17c]">{"// AI-generated fix"}</p>
                                        <p>&lt;img <span className="text-[#b7c6c2]">src</span>=&quot;hero.jpg&quot;</p>
                                        <p className="pl-4"><span className="text-[#ffe17c]">alt</span>=&quot;<span className="text-white">Accessible dashboard</span>&quot;</p>
                                        <p className="pl-4"><span className="text-[#ffe17c]">role</span>=&quot;<span className="text-white">img</span>&quot; /&gt;</p>
                                        <div className="mt-3 h-px bg-zinc-700" />
                                        <p className="text-[#ffe17c]">{"// Contrast fix"}</p>
                                        <p><span className="text-[#b7c6c2]">color</span>: <span className="text-white">#1a1a2e</span>;</p>
                                        <p><span className="text-[#b7c6c2]">background</span>: <span className="text-white">#ffffff</span>;</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="relative col-span-full overflow-hidden lg:col-span-3 border-2 border-black rounded-2xl bg-[#ffe17c]" style={{ boxShadow: '4px 4px 0px 0px #000' }}>
                            <CardContent className="grid h-full pt-6 sm:grid-cols-2">
                                <div className="relative z-10 flex flex-col justify-between space-y-12 lg:space-y-6">
                                    <div className="relative flex aspect-square size-12 rounded-full border-2 border-black before:absolute before:-inset-2 before:rounded-full before:border before:border-black/20">
                                        <Eye className="m-auto size-6 text-[#171e19]" strokeWidth={1.5} />
                                    </div>
                                    <div className="space-y-2">
                                        <h2 className="text-lg font-extrabold font-cabinet text-black transition">Visual Issue Explorer</h2>
                                        <p className="text-sm font-medium text-black/70">Interactively highlight violating DOM elements with overlays directly in the page context.</p>
                                    </div>
                                </div>
                                <div className="relative mt-6 sm:-my-6 sm:-mr-6">
                                    <div className="relative flex h-full flex-col justify-center space-y-5 py-6 pl-4">
                                        <div className="flex items-center gap-3">
                                            <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-black bg-white text-xs font-extrabold">47</div>
                                            <span className="rounded border-2 border-black bg-white px-3 py-1 text-xs font-bold">Missing alt text</span>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-black bg-white text-xs font-extrabold">33</div>
                                            <span className="rounded border-2 border-black bg-white px-3 py-1 text-xs font-bold">Low contrast</span>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-black bg-white text-xs font-extrabold">19</div>
                                            <span className="rounded border-2 border-black bg-white px-3 py-1 text-xs font-bold">Keyboard traps</span>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-black bg-[#b7c6c2] text-xs font-extrabold">12</div>
                                            <span className="rounded border-2 border-black bg-white px-3 py-1 text-xs font-bold">Missing landmarks</span>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </section>
    )
}
