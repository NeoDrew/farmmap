import MapView from './components/Map/MapView'
import FilterPanel from './components/FilterPanel/FilterPanel'
import CompanyPanel from './components/CompanyPanel/CompanyPanel'
import ViewportStats from './components/ViewportStats'
import ChoroplethInfo from './components/Map/ChoroplethInfo'

function App() {
  return (
    <div className="flex flex-col w-full h-screen overflow-hidden">
      {/* Top stats bar */}
      <ViewportStats />

      {/* Map area with overlaid panels */}
      <div className="relative flex-1 overflow-hidden">
        {/* Full-screen map */}
        <MapView />

        {/* Filter panel — top left overlay */}
        <div className="absolute top-3 left-3 z-[1000] pointer-events-auto">
          <FilterPanel />
        </div>

        {/* Choropleth legend — bottom right overlay (above Leaflet attribution) */}
        <div className="absolute bottom-8 right-3 z-[1000] pointer-events-none">
          <ChoroplethInfo />
        </div>

        {/* Company detail panel — slides in from right */}
        <CompanyPanel />
      </div>
    </div>
  )
}

export default App
