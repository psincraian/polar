import { useOrganizationSSE } from '@/hooks/sse'
import { setValidationErrors } from '@/utils/api/errors'
import { getQueryClient } from '@/utils/api/query'
import { api } from '@/utils/client'
import { isValidationError, type schemas } from '@polar-sh/client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'

export const useInvoiceDownload = ({
  organization,
  account,
  payout,
  onInvoiceGenerated,
  onClose,
}: {
  organization: schemas['Organization']
  account: schemas['Account']
  payout: schemas['Payout'] | null
  onInvoiceGenerated: () => void
  onClose: () => void
}) => {
  const [loading, setLoading] = useState(false)

  const form = useForm<
    schemas['AccountUpdate'] & schemas['PayoutGenerateInvoice']
  >({
    defaultValues: {
      ...account,
      invoice_number: payout?.invoice_number || '',
      billing_address: account.billing_address as
        | schemas['AddressInput']
        | null,
    },
  })

  const { setError, watch } = form
  const country = watch('billing_address.country')

  // Reset form when payout changes
  useEffect(() => {
    if (payout) {
      form.reset({
        ...account,
        invoice_number: payout.invoice_number || '',
        billing_address: account.billing_address as
          | schemas['AddressInput']
          | null,
      })
    }
  }, [payout, account, form])

  const downloadInvoice = useCallback(async () => {
    if (!payout) return

    setLoading(true)
    const response = await api.GET('/v1/payouts/{id}/invoice', {
      params: { path: { id: payout.id } },
    })
    if (response.error) {
      setLoading(false)
      return
    }

    // Trigger the download through a temporary anchor rather than
    // `window.open(url, '_blank')`. When this runs from the SSE handler (right
    // after generating the invoice) it's no longer inside the user's click
    // gesture, so browsers suppress the new tab as a popup and the file
    // silently never downloads. The invoice URL is served with
    // `Content-Disposition: attachment`, so a same-tab anchor click downloads
    // it without navigating away and isn't subject to popup blocking.
    const link = document.createElement('a')
    link.href = response.data.url
    link.rel = 'noopener'
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    link.remove()

    setLoading(false)
    onClose()
  }, [payout, onClose])

  const handleDownloadInvoice = useCallback(
    async (payout: schemas['Payout']) => {
      if (!payout.is_invoice_generated) {
        return false
      }

      await downloadInvoice()
      return true
    },
    [downloadInvoice],
  )

  // Guards against downloading twice when both the SSE event and the polling
  // fallback resolve for the same generation request.
  const awaitingGenerationRef = useRef(false)

  const completeGeneration = useCallback(() => {
    if (!awaitingGenerationRef.current) {
      return
    }
    awaitingGenerationRef.current = false
    onInvoiceGenerated()
    downloadInvoice()
  }, [onInvoiceGenerated, downloadInvoice])

  const onModalSubmit = useCallback(
    async (
      data: schemas['AccountUpdate'] & schemas['PayoutGenerateInvoice'],
    ) => {
      if (!payout) return

      setLoading(true)
      const { error } = await api.PATCH('/v1/accounts/{id}', {
        params: { path: { id: account.id } },
        body: data,
      })

      if (error) {
        if (isValidationError(error.detail)) {
          setValidationErrors(error.detail, setError)
        } else {
          setError('root', { message: error.detail })
        }
        setLoading(false)
        return
      }

      await getQueryClient().invalidateQueries({
        queryKey: ['organizations', 'account'],
      })

      awaitingGenerationRef.current = true
      const { error: generateError } = await api.POST(
        '/v1/payouts/{id}/invoice',
        {
          params: { path: { id: payout.id } },
          body: {
            invoice_number: data.invoice_number,
          },
        },
      )
      if (generateError) {
        awaitingGenerationRef.current = false
        if (isValidationError(generateError.detail)) {
          setValidationErrors(generateError.detail, setError)
        } else {
          setError('root', { message: generateError.detail })
        }
        setLoading(false)
        return
      }

      // The invoice is generated asynchronously and completion is normally
      // signalled over SSE, which triggers the download. If that event is
      // delayed or dropped the flow would otherwise hang on the loading
      // spinner forever, so poll the invoice as a fallback until it's ready.
      for (let attempt = 0; attempt < 30; attempt++) {
        if (!awaitingGenerationRef.current) {
          return
        }
        await new Promise((resolve) => setTimeout(resolve, 1000))
        if (!awaitingGenerationRef.current) {
          return
        }
        const { error: pollError } = await api.GET('/v1/payouts/{id}/invoice', {
          params: { path: { id: payout.id } },
        })
        if (!pollError) {
          completeGeneration()
          return
        }
      }

      if (awaitingGenerationRef.current) {
        awaitingGenerationRef.current = false
        setLoading(false)
        setError('root', {
          message:
            'The invoice is taking longer than expected to generate. Please try again in a moment.',
        })
      }
    },
    [payout, account, setError, completeGeneration],
  )

  const eventEmitter = useOrganizationSSE(organization.id)
  useEffect(() => {
    if (!payout) return

    const callback = ({ payout_id }: { payout_id: string }) => {
      if (payout_id === payout.id) {
        completeGeneration()
      }
    }
    eventEmitter.on('payout.invoice_generated', callback)
    return () => {
      eventEmitter.off('payout.invoice_generated', callback)
    }
  }, [eventEmitter, payout, completeGeneration])

  return {
    loading,
    form,
    country,
    handleDownloadInvoice,
    onModalSubmit,
    downloadInvoice,
  }
}
