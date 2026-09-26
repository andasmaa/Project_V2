import React, { useState, useEffect } from 'react'
import HITLCard from './HITLCard'
import { Clock, CheckCircle, XCircle, Users, TrendingUp, Shield } from 'lucide-react'

function SupervisorDashboard() {
  const [pendingRequests, setPendingRequests] = useState([
    {
      request_id: 'HITL-001',
      agent: 'AG06',
      agent_name: 'Credit',
      client: 'M. Ahmed Benali',
      type: 'Credit Request',
      context: 'Demande crédit immobilier de 150 000€',
      hitl_reason: 'Montant > 100k€',
      score: 0.72,
      proposed_action: 'approve',
      sla_remaining: 85,
      timestamp: new Date()
    },
    {
      request_id: 'HITL-002',
      agent: 'AG09',
      agent_name: 'Anti-Fraud',
      client: 'Mme. Fatima Zahra',
      type: 'Fraud Alert',
      context: 'Transaction suspecte de 12 450€',
      hitl_reason: 'Score fraude élevé: 0.89',
      score: 0.89,
      proposed_action: 'reject',
      sla_remaining: 15,
      timestamp: new Date()
    }
  ])
  const [selectedRequest, setSelectedRequest] = useState(null)
  const [stats, setStats] = useState({
    total_today: 12,
    approved: 8,
    rejected: 2,
    pending: 2,
    avg_response_time: 47
  })

  const handleApprove = async (requestId) => {
    setPendingRequests(prev => prev.filter(r => r.request_id !== requestId))
    setStats(prev => ({ ...prev, approved: prev.approved + 1, pending: prev.pending - 1 }))
    setSelectedRequest(null)
  }

  const handleReject = async (requestId) => {
    setPendingRequests(prev => prev.filter(r => r.request_id !== requestId))
    setStats(prev => ({ ...prev, rejected: prev.rejected + 1, pending: prev.pending - 1 }))
    setSelectedRequest(null)
  }

  return (
    <div className="p-6">
      {/* Stats Header */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="bg-white rounded-xl p-4 shadow-sm border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">Today</p>
              <p className="text-2xl font-bold text-gray-800">{stats.total_today}</p>
            </div>
            <Shield className="w-8 h-8 text-gray-300" />
          </div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">Approved</p>
              <p className="text-2xl font-bold text-green-600">{stats.approved}</p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-200" />
          </div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">Rejected</p>
              <p className="text-2xl font-bold text-red-600">{stats.rejected}</p>
            </div>
            <XCircle className="w-8 h-8 text-red-200" />
          </div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">Pending</p>
              <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
            </div>
            <Clock className="w-8 h-8 text-yellow-200" />
          </div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">Avg Response</p>
              <p className="text-2xl font-bold text-purple-600">{stats.avg_response_time}s</p>
            </div>
            <TrendingUp className="w-8 h-8 text-purple-200" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Requests List */}
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <div className="bg-gray-50 px-5 py-4 border-b">
            <h3 className="font-semibold flex items-center gap-2">
              <Clock className="w-4 h-4 text-yellow-600" />
              Pending HITL Requests ({pendingRequests.length})
            </h3>
          </div>
          <div className="divide-y max-h-[600px] overflow-y-auto">
            {pendingRequests.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
                <p>All requests processed</p>
              </div>
            ) : (
              pendingRequests.map((req) => (
                <div
                  key={req.request_id}
                  onClick={() => setSelectedRequest(req)}
                  className={`p-4 cursor-pointer hover:bg-gray-50 transition ${
                    selectedRequest?.request_id === req.request_id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                      req.agent === 'AG06' ? 'bg-indigo-100 text-indigo-700' :
                      req.agent === 'AG09' ? 'bg-red-100 text-red-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {req.agent_name} ({req.agent})
                    </span>
                    <span className="text-xs text-gray-400">
                      SLA: {req.sla_remaining}s
                    </span>
                  </div>
                  <p className="font-medium text-gray-800">{req.client}</p>
                  <p className="text-sm text-gray-600 mt-1">{req.context}</p>
                  <div className="mt-2 flex justify-between items-center">
                    <span className="text-xs text-gray-500">{req.hitl_reason}</span>
                    <span className="text-xs font-mono">Score: {Math.round(req.score * 100)}%</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* HITL Card Detail */}
        <div>
          <HITLCard 
            request={selectedRequest}
            onApprove={handleApprove}
            onReject={handleReject}
            onClose={() => setSelectedRequest(null)}
          />
        </div>
      </div>
    </div>
  )
}

export default SupervisorDashboard